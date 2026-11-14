"""Development-only relying party; browser cookies hold random references."""
import secrets

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import Field
from .api import ChallengeKind, Input, Service, remote_address
from .errors import require
from .models import Site
from .service import digest

router = APIRouter()


class DemoSessionInput(Input):
    challenge_type: ChallengeKind


class DemoTokenInput(Input):
    token: str = Field(min_length=1, max_length=200)


def demo_origin(request, settings):
    origin = request.headers.get("Origin", "")
    require(origin in settings.demo_origins, "ORIGIN_DENIED", "演示仅允许本地开发来源", 403)
    return origin


def demo_site_key(origin):
    return "site_local_demo" if origin in ("http://127.0.0.1:5178", "http://localhost:5178") else "site_local_hosted_demo"


@router.post("/demo/session", status_code=201)
def demo_session(data: DemoSessionInput, request: Request, service: Service):
    settings = service.settings
    origin = demo_origin(request, settings)
    service.rate_limit("demo_session", remote_address(request), 30)
    site = service.sites.get_or_create(Site(key=demo_site_key(origin), name="Local demonstration only",
                                           origins=list(settings.demo_origins), actions=["demo_submit"]))
    require(site.active, "SITE_INVALID", "演示站点已关闭", 403)
    context_id, browser_reference = secrets.token_urlsafe(24), secrets.token_urlsafe(32)
    result = service.create_session(site, "demo_submit", context_id, origin, data.challenge_type)
    service.redis.set(service.prefix + "demo-context:" + digest(browser_reference), context_id, ex=settings.session_ttl)
    response = JSONResponse(result, status_code=201)
    response.set_cookie("starlock_demo_context", browser_reference, max_age=settings.session_ttl,
                        httponly=True, samesite="strict", path="/demo/")
    return response


@router.post("/demo/submit")
def demo_submit(data: DemoTokenInput, request: Request, service: Service):
    origin = demo_origin(request, service.settings)
    service.rate_limit("demo_submit", remote_address(request), 60)
    reference = request.cookies.get("starlock_demo_context", "")
    require(1 <= len(reference) <= 128, "CONTEXT_MISMATCH", "演示会话已失效，请重新验证", 403)
    context_id = service.redis.get(service.prefix + "demo-context:" + digest(reference))
    require(context_id is not None, "CONTEXT_MISMATCH", "演示会话已失效，请重新验证", 403)
    result = service.consume(service.sites.get_active(demo_site_key(origin)), data.token, "demo_submit", context_id)
    return {**result, "message": "后端复核成功，本次演示请求已通过"}
