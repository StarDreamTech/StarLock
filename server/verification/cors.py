"""Only browser challenge routes opt into credential-free cross-origin access."""
import re
import sqlite3
import secrets

from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware


class ChallengeCors:
    def __init__(self, app, sites):
        self.app, self.sites = app, sites

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not re.fullmatch(
                r"/v1/challenges(?:/[^/]+/verify)?", scope["path"]):
            return await self.app(scope, receive, send)
        origin = dict(scope["headers"]).get(b"origin", b"").decode("latin-1")
        if not origin:
            return await self.app(scope, receive, send)
        try:
            allowed = await run_in_threadpool(self.sites.allows_origin, origin)
        except sqlite3.Error:
            return await JSONResponse({"error_code": "SERVICE_UNAVAILABLE", "message": "验证服务暂时不可用",
                                       "request_id": secrets.token_hex(8)}, status_code=503,
                                      headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})(scope, receive, send)
        cors = CORSMiddleware(self.app, allow_origins=[origin] if allowed else [],
                              allow_methods=["POST"], allow_headers=["Content-Type"],
                              allow_credentials=False, max_age=600)
        await cors(scope, receive, send)
