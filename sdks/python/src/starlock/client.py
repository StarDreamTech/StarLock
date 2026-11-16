"""Server-side HTTP client for StarLock sessions and one-time verification."""
import json
import math
import ssl
from dataclasses import dataclass
from http.client import HTTPException
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

ChallengeType = Literal["text", "digits", "arithmetic", "slider", "bezier_slider", "rotate", "text_click", "semantic_grid"]
MAX_RESPONSE_BYTES = 65_536


class StarLockError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 0,
                 request_id: str = "", retry_after: int | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.request_id = request_id
        self.retry_after = retry_after
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class Session:
    site_key: str
    session_ticket: str
    expires_in: int


@dataclass(frozen=True)
class VerificationResult:
    success: bool
    site_key: str
    action: str
    context_id: str
    hostname: str
    challenge_type: str
    verified_at: str


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


class Client:
    def __init__(self, *, api_base: str, site_key: str, site_secret: str,
                 timeout: float = 10, ssl_context: ssl.SSLContext | None = None):
        if not isinstance(api_base, str):
            raise ValueError("api_base must be an HTTP(S) URL")
        try:
            address = urlsplit(api_base)
            valid_address = (address.scheme in ("http", "https") and address.hostname and
                             address.username is None and address.password is None and not address.query and not address.fragment)
            address.port  # Validate a supplied port before making a request.
        except (TypeError, ValueError):
            valid_address = False
        if not valid_address or any(character in api_base for character in "?#") or any(character.isspace() for character in api_base):
            raise ValueError("api_base must be an HTTP(S) URL without credentials, query or fragment")
        if any(not isinstance(value, str) or not value or any(character in value for character in "\r\n")
               for value in (site_key, site_secret)):
            raise ValueError("site_key and site_secret must be nonempty single-line strings")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be a positive number of seconds")
        self.api_base = api_base.rstrip("/")
        self.site_key = site_key
        self._site_secret = site_secret
        self.timeout = timeout
        self._opener = build_opener(_NoRedirect(), HTTPSHandler(context=ssl_context))

    def _post(self, path: str, payload: dict) -> dict:
        request = Request(self.api_base + path, method="POST",
                          data=json.dumps({**payload, "site_key": self.site_key}).encode(),
                          headers={"Content-Type": "application/json", "Accept": "application/json",
                                   "User-Agent": "starlock-python/0.8.0", "Authorization": "Bearer " + self._site_secret})
        try:
            try:
                response = self._opener.open(request, timeout=self.timeout)
            except HTTPError as error:
                response = error
            with response:
                status = response.code
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (URLError, OSError, HTTPException):
            raise StarLockError("NETWORK_ERROR", "StarLock request failed; the operation outcome may be unknown") from None
        if 300 <= status < 400:
            raise StarLockError("REDIRECT_DENIED", "StarLock API redirects are disabled", status_code=status)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise StarLockError("PROTOCOL_ERROR", "StarLock response exceeded the size limit", status_code=status)
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise StarLockError("HTTP_ERROR" if not 200 <= status < 300 else "PROTOCOL_ERROR",
                                "StarLock returned invalid JSON", status_code=status) from None
        if not isinstance(data, dict):
            raise StarLockError("HTTP_ERROR" if not 200 <= status < 300 else "PROTOCOL_ERROR",
                                "StarLock returned an invalid response", status_code=status)
        if not 200 <= status < 300:
            retry_after = data.get("retry_after")
            raise StarLockError(data.get("error_code") if isinstance(data.get("error_code"), str) else "HTTP_ERROR",
                                data.get("message") if isinstance(data.get("message"), str) else "StarLock request was rejected",
                                status_code=status,
                                request_id=data.get("request_id") if isinstance(data.get("request_id"), str) else "",
                                retry_after=retry_after if type(retry_after) is int and retry_after >= 0 else None)
        return data

    def create_session(self, *, action: str, context_id: str, origin: str, challenge_type: ChallengeType = "text",
                       rotation_source: Literal["preset", "procedural"] | None = None,
                       image_set_id: str | None = None) -> Session:
        payload = {"action": action, "context_id": context_id, "origin": origin, "challenge_type": challenge_type}
        if rotation_source is not None:
            payload["rotation_source"] = rotation_source
        if image_set_id is not None:
            payload["image_set_id"] = image_set_id
        data = self._post("/v1/sessions", payload)
        if (data.get("site_key") != self.site_key or not isinstance(data.get("session_ticket"), str) or
                not data["session_ticket"] or type(data.get("expires_in")) is not int or data["expires_in"] <= 0):
            raise StarLockError("PROTOCOL_ERROR", "StarLock returned an invalid session")
        return Session(data["site_key"], data["session_ticket"], data["expires_in"])

    def siteverify(self, *, token: str, action: str, context_id: str) -> VerificationResult:
        data = self._post("/v1/siteverify", {"token": token, "action": action, "context_id": context_id})
        fields = ("hostname", "challenge_type", "verified_at")
        if (data.get("success") is not True or data.get("site_key") != self.site_key or
                data.get("action") != action or data.get("context_id") != context_id or
                any(not isinstance(data.get(field), str) or not data[field] for field in fields)):
            raise StarLockError("PROTOCOL_ERROR", "StarLock returned an invalid verification result")
        return VerificationResult(True, self.site_key, action, context_id, data["hostname"],
                                  data["challenge_type"], data["verified_at"])
