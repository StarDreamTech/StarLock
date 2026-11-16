"""Same-origin operator console. It never exposes site secrets or challenge answers."""
import hmac
import ipaddress
import secrets
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import Field
from starlette.concurrency import run_in_threadpool

from .api import ImageSetId, Input, Service, remote_address
from .errors import require
from .service import digest, normalize_origin

router = APIRouter(prefix="/admin", include_in_schema=False)
ASSETS = Path(__file__).resolve().parents[1] / "assets" / "admin"
COOKIE, TTL = "starlock_admin", 3600


def local_mode(request, service):
    try:
        loopback = ipaddress.ip_address(remote_address(request)).is_loopback
    except ValueError:
        loopback = False
    return service.settings.debug and service.settings.demo_enabled and loopback and not service.settings.admin_token


def same_origin(request):
    require(bool(request.headers.get("origin")), "ORIGIN_DENIED", "后台操作必须来自当前管理页面", 403)
    require(normalize_origin(request.headers["origin"]) == normalize_origin(str(request.base_url)),
            "ORIGIN_DENIED", "后台操作必须来自当前管理页面", 403)


def session_value(request, service):
    require(bool(service.settings.admin_token) or local_mode(request, service),
            "ADMIN_UNAVAILABLE", "请先在服务端配置 STARLOCK_ADMIN_TOKEN", 503)
    return digest(service.settings.admin_token or service.settings.secret_key)


def authenticated(request, service):
    cookie = request.cookies.get(COOKIE, "")
    if not 20 <= len(cookie) <= 128:
        return False
    expected = session_value(request, service)
    actual = service.redis.get(service.prefix + "admin:" + digest(cookie))
    return actual is not None and hmac.compare_digest(actual, expected)


def guard(request: Request, service: Service):
    require(authenticated(request, service), "ADMIN_AUTH_REQUIRED", "请先登录管理后台", 401)
    if request.method == "POST":
        same_origin(request)
    service.rate_limit("admin_write" if request.method == "POST" else "admin_read",
                       request.cookies.get(COOKIE, ""), 300 if request.method == "POST" else 1200)


class Login(Input):
    token: str = Field(default="", max_length=256)


class SetCreate(Input):
    name: str = Field(min_length=1, max_length=60)


class SetUpdate(SetCreate):
    active: bool


class DefaultSet(Input):
    set_id: ImageSetId


class ImageUpdate(Input):
    active: bool


@router.get("")
@router.get("/")
def console():
    return FileResponse(ASSETS / "index.html", headers={
        "X-Robots-Tag": "noindex, nofollow", "X-Frame-Options": "DENY",
        "Content-Security-Policy": "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"})


@router.get("/assets/{name}")
def asset(name: str):
    require(name in ("admin.css", "admin.js", "logo.svg"), "NOT_FOUND", "资源不存在", 404)
    return FileResponse(ASSETS / name)


@router.get("/api/status")
def status(request: Request, service: Service):
    enabled = bool(service.settings.admin_token) or local_mode(request, service)
    return {"local_mode": local_mode(request, service), "enabled": enabled,
            "authenticated": enabled and authenticated(request, service)}


@router.post("/api/login")
def login(data: Login, request: Request, service: Service):
    same_origin(request)
    service.rate_limit("admin_login", remote_address(request), 10)
    value = session_value(request, service)
    require(local_mode(request, service) or hmac.compare_digest(data.token.encode(), service.settings.admin_token.encode()),
            "ADMIN_AUTH_FAILED", "管理口令不正确", 403)
    old = request.cookies.get(COOKIE, "")
    if 20 <= len(old) <= 128:
        service.redis.delete(service.prefix + "admin:" + digest(old))
    cookie = secrets.token_urlsafe(32)
    service.redis.set(service.prefix + "admin:" + digest(cookie), value, ex=TTL)
    response = JSONResponse({"success": True})
    response.set_cookie(COOKIE, cookie, max_age=TTL, httponly=True, samesite="strict", path="/admin",
                        secure=not service.settings.debug or request.url.scheme == "https")
    return response


@router.post("/api/logout", dependencies=[Depends(guard)])
def logout(request: Request, service: Service):
    service.redis.delete(service.prefix + "admin:" + digest(request.cookies[COOKIE]))
    response = JSONResponse({"success": True})
    response.delete_cookie(COOKIE, path="/admin", httponly=True, samesite="strict")
    return response


@router.get("/api/sets", dependencies=[Depends(guard)])
def list_sets(service: Service):
    return service.image_sets.list()


@router.post("/api/sets", status_code=201, dependencies=[Depends(guard)])
def create_set(data: SetCreate, service: Service):
    return service.image_sets.create(data.name)


@router.get("/api/sets/{set_id}", dependencies=[Depends(guard)])
def detail(set_id: ImageSetId, service: Service):
    return service.image_sets.detail(set_id)


@router.post("/api/sets/{set_id}", dependencies=[Depends(guard)])
def update_set(set_id: ImageSetId, data: SetUpdate, service: Service):
    return service.image_sets.update(set_id, data.name, data.active)


@router.post("/api/default", dependencies=[Depends(guard)])
def default_set(data: DefaultSet, service: Service):
    return service.image_sets.set_default(data.set_id)


@router.post("/api/sets/{set_id}/images", status_code=201, dependencies=[Depends(guard)])
async def upload(set_id: ImageSetId, request: Request, service: Service):
    name = unquote(request.headers.get("x-file-name", "上传图片"))
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(c for c in name if c.isprintable()).strip()[:120] or "上传图片"
    raw = await request.body()
    return await run_in_threadpool(service.image_sets.upload, set_id, name, raw)


@router.post("/api/images/{asset_id}", dependencies=[Depends(guard)])
def update_image(asset_id: ImageSetId, data: ImageUpdate, service: Service):
    return service.image_sets.set_image_active(asset_id, data.active)


@router.get("/api/images/{asset_id}/preview", dependencies=[Depends(guard)])
def preview(asset_id: ImageSetId, service: Service):
    image = service.image_sets.image(asset_id)
    image.thumbnail((320, 320))
    stream = BytesIO()
    image.save(stream, "JPEG", quality=85)
    return Response(stream.getvalue(), media_type="image/jpeg")
