import hashlib
import hmac
import json
import math
import secrets
import time
from datetime import datetime, timezone
from functools import lru_cache
from urllib.parse import urlsplit

import redis
from redis.exceptions import WatchError

from .errors import VerificationError, require
from .generators import TYPES, generate
from .sliders import SLIDER_TYPES, matches_slider
from .rotations import matches_rotation
from .image_sets import ImageSetStore
from .selections import matches_text_click, matches_semantic_grid


@lru_cache(maxsize=4)
def connection(url):
    return redis.Redis.from_url(url, decode_responses=True,
                                socket_timeout=2, socket_connect_timeout=2)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def answer_digest(challenge_id, answer, secret_key):
    material = f"{challenge_id}:{answer.strip().upper()}".encode()
    return hmac.new(secret_key.encode(), material, hashlib.sha256).hexdigest()


def normalize_origin(value):
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise VerificationError("ORIGIN_INVALID", "无效的站点来源")
    require(parsed.scheme in ("http", "https") and parsed.hostname and
            parsed.path in ("", "/") and not parsed.query and not parsed.fragment and
            not parsed.username and not parsed.password, "ORIGIN_INVALID", "无效的站点来源")
    try:
        port = parsed.port
    except ValueError:
        raise VerificationError("ORIGIN_INVALID", "无效的来源端口")
    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    default_port = 443 if parsed.scheme == "https" else 80
    return f"{parsed.scheme}://{host}" + (f":{port}" if port and port != default_port else "")


class VerificationService:
    def __init__(self, settings, sites, client=None):
        self.settings = settings
        self.sites = sites
        self.redis = client if client is not None else connection(settings.redis_url)
        self.prefix = settings.redis_prefix
        self.image_sets = ImageSetStore(sites)

    def key(self, session_id):
        return self.prefix + "session:" + session_id

    def rate_limit(self, scope, identity, limit, seconds=60):
        key = self.prefix + "rate:" + scope + ":" + digest(identity)
        count = self.redis.eval("""
            local count = redis.call('INCR', KEYS[1])
            if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
            return count
        """, 1, key, seconds)
        if count > limit:
            raise VerificationError("RATE_LIMITED", "操作太频繁，请稍后重试", 429, retry_after=seconds)

    def create_session(self, site, action, context_id, origin, kind, rotation_source=None, image_set_id=None):
        origin = normalize_origin(origin)
        require(origin in site.origins, "ORIGIN_DENIED", "来源未获得站点授权", 403)
        require(action in site.actions, "ACTION_DENIED", "业务动作未获得站点授权", 403)
        require(kind in TYPES and kind in site.challenge_types, "TYPE_DENIED", "题型未获得站点授权", 403)
        require(rotation_source is None or (kind == "rotate" and rotation_source in ("preset", "procedural")),
                "INVALID_REQUEST", "旋转图片来源仅适用于圆环旋转题")
        require(image_set_id is None or kind in SLIDER_TYPES or (kind == "rotate" and rotation_source != "procedural"),
                "INVALID_REQUEST", "图片集仅适用于预设旋转题和拼图滑块")
        selected_set = (self.image_sets.resolve(image_set_id)
                        if image_set_id or (kind == "rotate" and rotation_source != "procedural") else None)
        sid, ticket_secret = secrets.token_urlsafe(24), secrets.token_urlsafe(32)
        ticket = sid + "." + ticket_secret
        now = time.time()
        state = {"site_key": site.key, "action": action, "context_id": context_id,
                 "origin": origin, "kind": kind, "ticket_hash": digest(ticket),
                 "status": "created", "expires_at": now + self.settings.session_ttl,
                 "challenge": None, "issued_count": 0}
        if kind == "rotate":
            state["rotation_source"] = rotation_source or "preset"
        if selected_set:
            state["image_set_id"] = selected_set
        require(self.redis.set(self.key(sid), json.dumps(state), ex=self.settings.session_ttl, nx=True),
                "BUSY", "请重试创建验证会话", 409)
        return {"site_key": site.key, "session_ticket": ticket, "expires_in": self.settings.session_ttl}

    def _sid(self, value):
        parts = value.split(".")
        require(len(parts) == 2 and all(parts) and len(value) <= 200,
                "SESSION_INVALID", "验证会话无效", 403)
        return parts[0]

    def read_ticket(self, ticket, site_key, origin):
        sid = self._sid(ticket)
        raw = self.redis.get(self.key(sid))
        require(raw is not None, "SESSION_EXPIRED", "验证会话已过期", 410)
        state = json.loads(raw)
        self._check_ticket(state, ticket, site_key, origin)
        site = self.sites.get_active(site_key)
        require(origin in site.origins, "ORIGIN_DENIED", "来源未获得站点授权", 403)
        require(state["action"] in site.actions and state["kind"] in site.challenge_types,
                "POLICY_CHANGED", "站点策略已变更，请重新验证", 403)
        return sid, state

    def _check_ticket(self, state, ticket, site_key, origin):
        require(state["expires_at"] > time.time(), "SESSION_EXPIRED", "验证会话已过期", 410)
        require(hmac.compare_digest(state["ticket_hash"], digest(ticket)) and
                state["site_key"] == site_key, "SESSION_INVALID", "验证会话无效", 403)
        require(origin == state["origin"], "ORIGIN_DENIED", "来源与验证会话不匹配", 403)

    def _change(self, sid, change):
        key = self.key(sid)
        for _ in range(12):
            with self.redis.pipeline() as pipe:
                try:
                    pipe.watch(key)
                    raw = pipe.get(key)
                    require(raw is not None, "SESSION_EXPIRED", "验证会话已过期", 410)
                    state = json.loads(raw)
                    require(state["expires_at"] > time.time(), "SESSION_EXPIRED", "验证会话已过期", 410)
                    result = change(state)
                    pipe.multi()
                    pipe.set(key, json.dumps(state), keepttl=True)
                    pipe.execute()
                    if isinstance(result, VerificationError):
                        raise result
                    return result
                except WatchError:
                    continue
        raise VerificationError("BUSY", "验证正在处理中，请重试", 409)

    def challenge(self, ticket, site_key, origin, replace=None):
        sid, _ = self.read_ticket(ticket, site_key, origin)
        self.rate_limit("challenge", sid, 10)

        def change(state):
            self._check_ticket(state, ticket, site_key, origin)
            require(state["status"] in ("created", "active"), "SESSION_CLOSED", "请创建新的验证会话", 409)
            old = state["challenge"]
            if old and replace is None and old["expires_at"] > time.time() and not old["closed"]:
                return self._public_challenge(old, state["kind"])
            if old:
                require(replace == old["id"], "CHALLENGE_REPLACED", "请刷新当前题目", 409)
            require(state["issued_count"] < 10, "ATTEMPTS_EXCEEDED", "会话出题次数已用完，请重新开始", 429)
            options = {"rotation_source": state.get("rotation_source", "procedural")} if state["kind"] == "rotate" else {}
            if state.get("image_set_id"):
                options["image"] = self.image_sets.sample(state["image_set_id"])
            generated = generate(state["kind"], **options)
            challenge_id = "ch_" + secrets.token_urlsafe(24)
            state["challenge"] = {
                "id": challenge_id,
                "answer_hash": answer_digest(challenge_id, generated.answer, self.settings.secret_key) if generated.solution is None else None,
                "solution": generated.solution,
                "payload": generated.payload, "attempts": 0, "closed": False,
                "expires_at": min(time.time() + self.settings.challenge_ttl, state["expires_at"]),
            }
            state["status"] = "active"
            state["issued_count"] += 1
            return self._public_challenge(state["challenge"], state["kind"])
        return self._change(sid, change)

    @staticmethod
    def _public_challenge(challenge, kind):
        return {"decision": "challenge", "challenge_id": challenge["id"], "challenge_type": kind,
                "expires_in": max(0, math.floor(challenge["expires_at"] - time.time())),
                "payload": challenge["payload"]}

    def verify(self, ticket, site_key, origin, challenge_id, answer):
        sid, _ = self.read_ticket(ticket, site_key, origin)
        self.rate_limit("answer", sid, 20)

        def change(state):
            self._check_ticket(state, ticket, site_key, origin)
            require(state["status"] == "active", "SESSION_CLOSED", "请创建新的验证会话", 409)
            challenge = state["challenge"]
            require(challenge and challenge["id"] == challenge_id,
                    "CHALLENGE_REPLACED", "题目已刷新，请使用新题", 409)
            require(challenge["expires_at"] > time.time(), "CHALLENGE_EXPIRED", "题目已过期，请刷新", 410)
            require(not challenge["closed"], "ATTEMPTS_EXCEEDED", "本题尝试次数已用完，请刷新", 429)
            if state["kind"] == "rotate":
                valid = matches_rotation(challenge["payload"], challenge["solution"], answer)
            elif state["kind"] == "text_click":
                valid = matches_text_click(challenge["payload"], challenge["solution"], answer)
            elif state["kind"] == "semantic_grid":
                valid = matches_semantic_grid(challenge["payload"], challenge["solution"], answer)
            elif state["kind"] in SLIDER_TYPES:
                valid = matches_slider(challenge["payload"], challenge["solution"], answer)
            else:
                valid = isinstance(answer, str) and hmac.compare_digest(
                    challenge["answer_hash"], answer_digest(challenge_id, answer, self.settings.secret_key))
            if not valid:
                challenge["attempts"] += 1
                remaining = self.settings.max_attempts - challenge["attempts"]
                challenge["closed"] = remaining <= 0
                return VerificationError("ATTEMPTS_EXCEEDED" if remaining <= 0 else "ANSWER_INVALID",
                                         "本题尝试次数已用完，请刷新" if remaining <= 0 else "答案不正确，请再试一次",
                                         429 if remaining <= 0 else 400, attempts_remaining=max(0, remaining))
            token = sid + "." + secrets.token_urlsafe(32)
            now = time.time()
            state["token_hash"] = digest(token)
            state["token_expires_at"] = min(now + self.settings.token_ttl, state["expires_at"])
            state["verified_at"] = datetime.now(timezone.utc).isoformat()
            state["status"] = "passed"
            state["challenge"] = None  # Drop answer material and image after success.
            return {"verification_token": token, "expires_in": max(0, math.floor(state["token_expires_at"] - now))}
        return self._change(sid, change)

    def consume(self, site, token, action, context_id):
        sid = self._sid(token)

        def change(state):
            require(state["site_key"] == site.key and hmac.compare_digest(state.get("token_hash", ""), digest(token)),
                    "TOKEN_INVALID", "验证凭证无效", 403)
            require(state["action"] == action and state["context_id"] == context_id,
                    "CONTEXT_MISMATCH", "凭证与当前业务不匹配", 403)
            require(state["status"] != "consumed", "TOKEN_USED", "验证凭证已使用", 409)
            require(state["status"] == "passed" and state["token_expires_at"] > time.time(),
                    "TOKEN_EXPIRED", "验证凭证已过期", 410)
            state["status"] = "consumed"
            return {"success": True, "site_key": site.key, "action": action, "context_id": context_id,
                    "hostname": urlsplit(state["origin"]).hostname, "challenge_type": state["kind"],
                    "verified_at": state["verified_at"]}
        return self._change(sid, change)
