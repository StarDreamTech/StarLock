import json
import secrets
import time
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
from redis.exceptions import ConnectionError

from config.settings import Settings
from verification.api import create_app
from verification.errors import VerificationError
from verification.generators import TYPES, generate
from verification.models import Site, SiteStore
from verification.service import VerificationService, answer_digest, normalize_origin

ORIGIN = "http://127.0.0.1:5178"


class GeneratorTests(TestCase):
    def test_images_and_answers(self):
        import base64
        for kind in ("text", "digits", "arithmetic"):
            for _ in range(10):
                generated = generate(kind)
                image = Image.open(BytesIO(base64.b64decode(generated.payload["image"].split(",")[1])))
                self.assertEqual(image.size, (280, 88))
                self.assertNotIn("answer", generated.payload)
                if kind == "digits":
                    self.assertTrue(generated.answer.isdecimal())
                    self.assertEqual(len(generated.answer), 5)
                elif kind == "arithmetic":
                    self.assertTrue(0 <= int(generated.answer) <= 18)
                else:
                    self.assertEqual(len(generated.answer), 5)

    def test_unknown_type_and_origin_validation(self):
        with self.assertRaises(ValueError):
            generate("invisible")
        self.assertEqual(normalize_origin("https://Example.com:443/"), "https://example.com")
        for value in ("https://example.com/path", "https://user:pass@example.com", "http://[", "file://host"):
            with self.assertRaises(VerificationError):
                normalize_origin(value)

    def test_arithmetic_uses_correct_operations_and_nonnegative_subtraction(self):
        for operator, expected in (("+", "11"), ("-", "3")):
            with patch("verification.generators.secrets.randbelow", side_effect=[3, 6]), \
                 patch("verification.generators.secrets.choice", return_value=operator):
                self.assertEqual(generate("arithmetic").answer, expected)


class VerificationTests(TestCase):
    def setUp(self):
        self.prefix = "starlock:test:" + secrets.token_hex(8) + ":"
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.settings = Settings(debug=True, redis_prefix=self.prefix, database_path=Path(directory) / "sites.sqlite3")
        self.store = SiteStore(self.settings.database_path)
        self.store.initialize()
        self.service = VerificationService(self.settings, self.store)
        self.service.redis.ping()  # These tests intentionally require a real, isolated Redis namespace.
        self.addCleanup(self.clean_keys)
        self.secret = "ss_" + secrets.token_urlsafe(32)
        self.site = Site(key="site_test", name="Test", origins=[ORIGIN], actions=["register", "login"])
        self.site.set_secret(self.secret)
        self.store.save(self.site)
        self.client = self.enterContext(TestClient(create_app(self.settings, self.store)))
        generated = replace(generate("text"), answer="ABCDE")
        self.generator = patch("verification.service.generate", return_value=generated)
        self.generator.start()
        self.addCleanup(self.generator.stop)

    def clean_keys(self):
        keys = list(self.service.redis.scan_iter(self.prefix + "*"))
        if keys:
            self.service.redis.delete(*keys)

    def session(self):
        result = self.service.create_session(self.site, "register", "context_test_12345", ORIGIN, "text")
        return result["session_ticket"]

    def challenge(self, ticket):
        return self.service.challenge(ticket, self.site.key, ORIGIN)

    def passed(self):
        ticket = self.session()
        challenge = self.challenge(ticket)
        token = self.service.verify(ticket, self.site.key, ORIGIN, challenge["challenge_id"], "abcde")
        return ticket, token["verification_token"]

    def edit_state(self, ticket, **changes):
        key = self.service.key(ticket.split(".")[0])
        state = json.loads(self.service.redis.get(key))
        state.update(changes)
        self.service.redis.set(key, json.dumps(state), keepttl=True)
        return state

    def test_complete_http_flow_without_answer_leak(self):
        response = self.client.post("/v1/sessions", json={
            "site_key": self.site.key, "action": "register", "context_id": "context_test_12345",
            "origin": ORIGIN, "challenge_type": "text",
        }, headers={"Authorization": "Bearer " + self.secret})
        self.assertEqual(response.status_code, 201)
        browser = {"site_key": self.site.key, "session_ticket": response.json()["session_ticket"]}
        challenge = self.client.post("/v1/challenges", json=browser, headers={"Origin": ORIGIN})
        self.assertEqual(challenge.status_code, 200)
        self.assertEqual(challenge.headers["Cache-Control"], "no-store")
        self.assertNotIn("answer", challenge.json())
        self.assertNotIn("text", challenge.json()["payload"])
        state = json.loads(self.service.redis.get(self.service.key(browser["session_ticket"].split(".")[0])))
        self.assertEqual(state["challenge"]["answer_hash"], answer_digest(challenge.json()["challenge_id"], "ABCDE", self.settings.secret_key))
        self.assertNotIn('"ABCDE"', json.dumps(state))
        verify = self.client.post(f'/v1/challenges/{challenge.json()["challenge_id"]}/verify',
                                  json={**browser, "answer": "ABCDE"}, headers={"Origin": ORIGIN})
        self.assertEqual(verify.status_code, 200)
        result = self.client.post("/v1/siteverify", json={"site_key": self.site.key,
            "token": verify.json()["verification_token"], "action": "register", "context_id": "context_test_12345"},
            headers={"Authorization": "Bearer " + self.secret})
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()["success"])

    def test_origin_and_ticket_binding(self):
        ticket = self.session()
        for key, origin, value in (("site_other", ORIGIN, ticket), (self.site.key, "https://evil.example", ticket),
                                   (self.site.key, ORIGIN, ticket + "x")):
            with self.assertRaises(VerificationError):
                self.service.challenge(value, key, origin)
        self.site.active = False
        self.store.save(self.site)
        with self.assertRaises(VerificationError):
            self.challenge(ticket)

    def test_refresh_invalidates_old_challenge(self):
        ticket = self.session()
        first = self.challenge(ticket)
        self.assertEqual(first["challenge_id"], self.challenge(ticket)["challenge_id"])
        second = self.service.challenge(ticket, self.site.key, ORIGIN, first["challenge_id"])
        self.assertNotEqual(first["challenge_id"], second["challenge_id"])
        with self.assertRaises(VerificationError) as error:
            self.service.verify(ticket, self.site.key, ORIGIN, first["challenge_id"], "ABCDE")
        self.assertEqual(error.exception.code, "CHALLENGE_REPLACED")

    def test_failed_attempts_persist_and_cap(self):
        ticket = self.session()
        challenge = self.challenge(ticket)
        for remaining in (2, 1, 0):
            with self.assertRaises(VerificationError) as error:
                self.service.verify(ticket, self.site.key, ORIGIN, challenge["challenge_id"], "WRONG")
            self.assertEqual(error.exception.details["attempts_remaining"], remaining)
        with self.assertRaises(VerificationError) as error:
            self.service.verify(ticket, self.site.key, ORIGIN, challenge["challenge_id"], "ABCDE")
        self.assertEqual(error.exception.code, "ATTEMPTS_EXCEEDED")

    def test_challenge_token_and_session_expiration(self):
        ticket = self.session()
        challenge = self.challenge(ticket)
        state = json.loads(self.service.redis.get(self.service.key(ticket.split(".")[0])))
        state["challenge"]["expires_at"] = time.time() - 1
        self.edit_state(ticket, challenge=state["challenge"])
        with self.assertRaises(VerificationError) as error:
            self.service.verify(ticket, self.site.key, ORIGIN, challenge["challenge_id"], "ABCDE")
        self.assertEqual(error.exception.code, "CHALLENGE_EXPIRED")
        ticket, token = self.passed()
        self.edit_state(ticket, token_expires_at=time.time() - 1)
        with self.assertRaises(VerificationError) as error:
            self.service.consume(self.site, token, "register", "context_test_12345")
        self.assertEqual(error.exception.code, "TOKEN_EXPIRED")
        self.edit_state(ticket, expires_at=time.time() - 1)
        with self.assertRaises(VerificationError) as error:
            self.challenge(ticket)
        self.assertEqual(error.exception.code, "SESSION_EXPIRED")

    def test_wrong_context_and_site_do_not_consume(self):
        _, token = self.passed()
        for action, context in (("login", "context_test_12345"), ("register", "different_context")):
            with self.assertRaises(VerificationError) as error:
                self.service.consume(self.site, token, action, context)
            self.assertEqual(error.exception.code, "CONTEXT_MISMATCH")
        other = Site(key="site_other", name="Other")
        with self.assertRaises(VerificationError):
            self.service.consume(other, token, "register", "context_test_12345")
        self.assertTrue(self.service.consume(self.site, token, "register", "context_test_12345")["success"])

    def test_concurrent_consumption_has_one_winner(self):
        _, token = self.passed()
        def consume(_):
            try:
                return self.service.consume(self.site, token, "register", "context_test_12345")["success"]
            except VerificationError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(consume, range(8)))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count("TOKEN_USED"), 7)

    def test_only_one_token_and_no_refresh_after_pass(self):
        ticket, _ = self.passed()
        with self.assertRaises(VerificationError) as error:
            self.challenge(ticket)
        self.assertEqual(error.exception.code, "SESSION_CLOSED")

    def test_limits_and_unavailable_service(self):
        for _ in range(3):
            self.service.rate_limit("sample", "user", 3)
        with self.assertRaises(VerificationError) as error:
            self.service.rate_limit("sample", "user", 3)
        self.assertEqual(error.exception.code, "RATE_LIMITED")
        with patch("redis.Redis.ping", side_effect=ConnectionError("unavailable")):
            response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error_code"], "SERVICE_UNAVAILABLE")

    def test_authentication_and_request_validation(self):
        body = {"site_key": self.site.key, "origin": ORIGIN, "context_id": "context_test_12345", "action": "register"}
        self.assertEqual(self.client.post("/v1/sessions", json=body).status_code, 403)
        self.assertEqual(self.client.post("/v1/sessions", json={**body, "challenge_type": "invisible"}).status_code, 400)
        response = self.client.post("/v1/challenges", content='{"broken"', headers={"Content-Type": "application/json"})
        self.assertEqual(response.json()["error_code"], "INVALID_REQUEST")
        response = self.client.post("/v1/challenges", json={"unused": "x" * 40000})
        self.assertEqual(response.status_code, 413)

    def test_demo_routes_absent_by_default(self):
        self.assertEqual(self.client.post("/demo/session", json={}).status_code, 404)

    def test_concurrent_verification_issues_one_token(self):
        ticket = self.session()
        challenge_id = self.challenge(ticket)["challenge_id"]
        def verify(_):
            try:
                return self.service.verify(ticket, self.site.key, ORIGIN, challenge_id, "ABCDE")
            except VerificationError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(verify, range(8)))
        self.assertEqual(sum(isinstance(result, dict) for result in results), 1)
        self.assertEqual(results.count("SESSION_CLOSED"), 7)

    def test_chunked_body_is_bounded_and_validation_does_not_echo_tokens(self):
        response = self.client.post("/v1/challenges", content=iter([b"x" * 20000, b"y" * 20000]),
                                    headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 413)
        marker = "not-a-real-session-ticket"
        response = self.client.post("/v1/challenges", json={"session_ticket": marker})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(marker, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.client.post("/v1/challenges", content="plain text").status_code, 415)

    def test_openapi_and_host_guard(self):
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/v1/siteverify", schema["paths"])
        self.assertNotIn("/demo/session", schema["paths"])
        self.assertEqual(self.client.get("/healthz", headers={"Host": "evil.example"}).status_code, 400)

    def test_registered_origins_get_credential_free_cors_preflight(self):
        headers = {"Origin": ORIGIN, "Access-Control-Request-Method": "POST",
                   "Access-Control-Request-Headers": "content-type"}
        for path in ("/v1/challenges", "/v1/challenges/ch_example/verify"):
            response = self.client.options(path, headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["access-control-allow-origin"], ORIGIN)
            self.assertIn("Origin", response.headers["vary"])
            self.assertNotIn("access-control-allow-credentials", response.headers)
        response = self.client.options("/v1/challenges", headers={**headers,
            "Access-Control-Request-Headers": "authorization"})
        self.assertEqual(response.status_code, 400)
        response = self.client.options("/v1/challenges", headers={**headers, "Access-Control-Request-Method": "DELETE"})
        self.assertEqual(response.status_code, 400)

    def test_unregistered_and_disabled_origins_have_no_cors_access(self):
        headers = {"Origin": "https://unregistered.example", "Access-Control-Request-Method": "POST"}
        response = self.client.options("/v1/challenges", headers=headers)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)
        self.site.active = False
        self.store.save(self.site)
        response = self.client.options("/v1/challenges", headers={**headers, "Origin": ORIGIN})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_server_only_endpoints_do_not_opt_into_cors(self):
        for path in ("/v1/sessions", "/v1/siteverify"):
            preflight = self.client.options(path, headers={"Origin": ORIGIN,
                "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type,authorization"})
            self.assertNotIn("access-control-allow-origin", preflight.headers)
            response = self.client.post(path, json={}, headers={"Origin": ORIGIN})
            self.assertNotIn("access-control-allow-origin", response.headers)

    def test_cors_keeps_ticket_origin_binding_and_error_responses_readable(self):
        ticket = self.session()
        other = "https://other.example"
        self.store.save(Site(name="Another registered site", origins=[other]))
        browser = {"site_key": self.site.key, "session_ticket": ticket}
        response = self.client.post("/v1/challenges", json=browser, headers={"Origin": other})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error_code"], "ORIGIN_DENIED")
        self.assertEqual(response.headers["access-control-allow-origin"], other)
        challenge = self.client.post("/v1/challenges", json=browser, headers={"Origin": ORIGIN})
        path = f'/v1/challenges/{challenge.json()["challenge_id"]}/verify'
        invalid = self.client.post(path, json={**browser, "answer": "wrong"}, headers={"Origin": ORIGIN})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.headers["access-control-allow-origin"], ORIGIN)
        self.assertEqual(invalid.headers["cache-control"], "no-store")
        passed = self.client.post(path, json={**browser, "answer": "ABCDE"}, headers={"Origin": ORIGIN})
        self.assertEqual(passed.status_code, 200)
        self.assertEqual(passed.headers["access-control-allow-origin"], ORIGIN)

    def test_cors_does_not_strip_headers_from_bounded_request_errors(self):
        response = self.client.post("/v1/challenges", json={"large": "x" * 40000}, headers={"Origin": ORIGIN})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.headers["access-control-allow-origin"], ORIGIN)

    def test_sdk_serves_only_the_built_script_with_short_public_cache(self):
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (directory / "v1").mkdir()
        (directory / "v1/api.js").write_text("window.StarLock={version:'test'}")
        settings = replace(self.settings, sdk_directory=directory)
        with TestClient(create_app(settings, self.store)) as client:
            script = client.get("/sdk/v1/api.js")
            self.assertEqual(script.status_code, 200)
            self.assertIn("javascript", script.headers["content-type"])
            self.assertEqual(script.headers["cache-control"], "public, max-age=300")
            self.assertEqual(script.headers["cross-origin-resource-policy"], "cross-origin")
            head = client.head("/sdk/v1/api.js")
            self.assertEqual(head.status_code, 200)
            self.assertEqual(head.content, b"")
            self.assertEqual(client.get("/sdk/v1/other.js").status_code, 404)
            self.assertEqual(client.get("/sdk/db.sqlite3").status_code, 404)
        with TestClient(create_app(replace(settings, sdk_directory=directory / "missing"), self.store)) as client:
            missing = client.get("/sdk/v1/api.js")
            self.assertEqual(missing.status_code, 503)
            self.assertEqual(missing.json()["error_code"], "SDK_NOT_BUILT")
            self.assertEqual(missing.headers["cache-control"], "no-store")
