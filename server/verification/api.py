import secrets
import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from redis.exceptions import RedisError
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from config.settings import Settings
from .errors import VerificationError, require
from .cors import ChallengeCors
from .models import SiteStore
from .service import VerificationService


def error_response(code, message, status, **details):
    headers = {"Retry-After": str(details["retry_after"])} if code == "RATE_LIMITED" else None
    return JSONResponse({"error_code": code, "message": message,
                         "request_id": secrets.token_hex(8), **details}, status_code=status, headers=headers)


class ApiBoundary:
    """Bound request bytes before JSON parsing, including chunked requests."""
    def __init__(self, app, max_body_bytes):
        self.app, self.max_body_bytes = app, max_body_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def secured_send(message):
            if message["type"] == "http.response.start":
                headers = {key.lower(): value for key, value in message.get("headers", [])}
                headers.update({b"cache-control": b"no-store", b"x-content-type-options": b"nosniff",
                                b"referrer-policy": b"same-origin"})
                if scope["path"] == "/sdk/v1/api.js" and message["status"] in (200, 206, 304):
                    headers[b"cache-control"] = b"public, max-age=300"
                    headers[b"cross-origin-resource-policy"] = b"cross-origin"
                message = {**message, "headers": list(headers.items())}
            await send(message)

        if scope["method"] == "POST":
            headers = dict(scope["headers"])
            content_type = headers.get(b"content-type", b"").split(b";", 1)[0].strip().lower()
            if content_type != b"application/json":
                return await error_response("INVALID_REQUEST", "请求必须使用 JSON 格式", 415)(scope, receive, secured_send)
            try:
                length = int(headers.get(b"content-length", b"0"))
                if length < 0:
                    raise ValueError
            except ValueError:
                return await error_response("INVALID_REQUEST", "请求格式不正确", 400)(scope, receive, secured_send)
            body = bytearray()
            if length > self.max_body_bytes:
                return await error_response("INVALID_REQUEST", "请求内容过大", 413)(scope, receive, secured_send)
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > self.max_body_bytes:
                    return await error_response("INVALID_REQUEST", "请求内容过大", 413)(scope, receive, secured_send)
                if not message.get("more_body", False):
                    break
            delivered = False

            async def buffered_receive():
                nonlocal delivered
                if delivered:
                    return await receive()
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            return await self.app(scope, buffered_receive, secured_send)
        return await self.app(scope, receive, secured_send)


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, strict=True, extra="forbid")


ChallengeKind = Literal["text", "digits", "arithmetic", "slider", "bezier_slider", "rotate"]


class SessionInput(Input):
    site_key: str = Field(min_length=1, max_length=80)
    action: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    context_id: str = Field(min_length=12, max_length=128)
    origin: str = Field(min_length=1, max_length=250)
    challenge_type: ChallengeKind = "text"


class BrowserInput(Input):
    site_key: str = Field(min_length=1, max_length=80)
    session_ticket: str = Field(min_length=1, max_length=200)
    replace_challenge_id: str | None = Field(default=None, min_length=1, max_length=80)


class SliderAnswer(Input):
    progress: float = Field(ge=0, le=1, allow_inf_nan=False)


class AnswerInput(BrowserInput):
    answer: Annotated[str, Field(min_length=1, max_length=32)] | SliderAnswer


class ConsumeInput(Input):
    site_key: str = Field(min_length=1, max_length=80)
    token: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=64)
    context_id: str = Field(min_length=1, max_length=128)


def service_for(request: Request):
    return request.app.state.service


Service = Annotated[VerificationService, Depends(service_for)]


def remote_address(request):
    return request.client.host if request.client else "unknown"


def authenticate_site(request, service, site_key):
    service.rate_limit("auth", remote_address(request), 120)
    site = service.sites.get_active(site_key)
    authorization = request.headers.get("Authorization", "")
    require(authorization.startswith("Bearer ") and 20 <= len(authorization) <= 220,
            "SITE_AUTH_FAILED", "站点认证失败", 403)
    require(site.accepts_secret(authorization[7:]), "SITE_AUTH_FAILED", "站点认证失败", 403)
    return site


router = APIRouter()


@router.post("/v1/sessions", status_code=201)
def create_session(data: SessionInput, request: Request, service: Service):
    site = authenticate_site(request, service, data.site_key)
    service.rate_limit("session_site", site.key, 120)
    return service.create_session(site, data.action, data.context_id, data.origin, data.challenge_type)


@router.post("/v1/challenges")
def create_challenge(data: BrowserInput, request: Request, service: Service):
    return service.challenge(data.session_ticket, data.site_key, request.headers.get("Origin", ""),
                             data.replace_challenge_id)


@router.post("/v1/challenges/{challenge_id}/verify")
def verify_challenge(data: AnswerInput, challenge_id: str, request: Request, service: Service):
    require(len(challenge_id) <= 80, "INVALID_REQUEST", "题目标识无效")
    return service.verify(data.session_ticket, data.site_key, request.headers.get("Origin", ""),
                          challenge_id, data.answer.model_dump() if isinstance(data.answer, SliderAnswer) else data.answer)


@router.post("/v1/siteverify")
def siteverify(data: ConsumeInput, request: Request, service: Service):
    site = authenticate_site(request, service, data.site_key)
    service.rate_limit("consume_site", site.key, 240)
    return service.consume(site, data.token, data.action, data.context_id)


@router.get("/healthz")
def health(service: Service):
    service.redis.ping()
    return {"status": "ok"}


def create_app(settings=None, sites=None, redis_client=None):
    settings = settings or Settings.from_env()
    sites = sites or SiteStore(settings.database_path)

    @asynccontextmanager
    async def lifespan(app):
        await run_in_threadpool(sites.initialize)
        yield

    app = FastAPI(title="StarLock API", version="0.7.0", lifespan=lifespan,
                  docs_url="/docs" if settings.debug else None, redoc_url=None,
                  openapi_url="/openapi.json" if settings.debug else None)
    app.state.service = VerificationService(settings, sites, client=redis_client)
    app.add_middleware(ApiBoundary, max_body_bytes=settings.max_body_bytes)
    app.add_middleware(ChallengeCors, sites=sites)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts), www_redirect=False)

    @app.exception_handler(VerificationError)
    async def verification_error(request, error):
        return error_response(error.code, error.message, error.status, **error.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Validation errors contain submitted tokens; never echo their input values.
        return error_response("INVALID_REQUEST", "请求格式不正确", 400)

    @app.exception_handler(RedisError)
    @app.exception_handler(sqlite3.Error)
    async def unavailable(request, error):
        return error_response("SERVICE_UNAVAILABLE", "验证服务暂时不可用，请稍后重试", 503)

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return error_response("INVALID_REQUEST", "接口不存在或请求方式不正确", error.status_code)

    app.include_router(router)

    @app.api_route("/sdk/v1/api.js", methods=["GET", "HEAD"], include_in_schema=False)
    def browser_sdk():
        path = settings.sdk_directory / "v1" / "api.js"
        require(path.is_file(), "SDK_NOT_BUILT", "请先运行 npm run build:sdk", 503)
        return FileResponse(path, media_type="text/javascript")

    if settings.demo_enabled:
        from .demo import router as demo_router
        app.include_router(demo_router)
    return app
