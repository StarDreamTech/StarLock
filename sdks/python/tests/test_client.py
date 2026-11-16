import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import TestCase

from starlock import Client, StarLockError

FIXTURE = json.loads((Path(__file__).resolve().parents[3] / 'sdks/go/testdata/server-sdk.json').read_text())
SECRET = 'ss_example_for_sdk_tests_only'


class ClientTests(TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                self.server.requests.append((self.path, request, self.headers))
                time.sleep(self.server.delay)
                status, data = self.server.reply(self.path)
                encoded = data if isinstance(data, bytes) else json.dumps(data).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(encoded)))
                if status in (301, 302, 303, 307, 308):
                    self.send_header('Location', '/unexpected')
                self.end_headers()
                try:
                    self.wfile.write(encoded)
                except BrokenPipeError:
                    pass

            def log_message(self, *args):
                pass
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.server.requests = []
        self.server.delay = 0
        self.server.reply = lambda path: (201, FIXTURE['session']) if path.endswith('/sessions') else (200, FIXTURE['verification'])
        self.base = f'http://127.0.0.1:{self.server.server_port}/starlock/'
        self.client = Client(api_base=self.base, site_key=FIXTURE['site_key'], site_secret=SECRET)

    def test_session_options_and_verified_binding_use_the_same_protocol(self):
        session = self.client.create_session(action='login', context_id='context_sdk_example_123',
            origin='https://app.example.com', challenge_type='rotate', rotation_source='preset', image_set_id='system-orbit')
        self.assertEqual(session.session_ticket, 'session.example')
        self.assertEqual(session.expires_in, 300)
        path, body, headers = self.server.requests[0]
        self.assertEqual(path, '/starlock/v1/sessions')
        self.assertEqual(body, {'site_key': FIXTURE['site_key'], 'action': 'login', 'context_id': 'context_sdk_example_123',
            'origin': 'https://app.example.com', 'challenge_type': 'rotate', 'rotation_source': 'preset', 'image_set_id': 'system-orbit'})
        self.assertEqual(headers['Authorization'], 'Bearer ' + SECRET)
        result = self.client.siteverify(token='token.example', action='login', context_id='context_sdk_example_123')
        self.assertTrue(result.success)
        self.assertEqual(result.challenge_type, 'semantic_grid')
        self.assertEqual(self.server.requests[1][0], '/starlock/v1/siteverify')
        self.assertNotIn(SECRET, json.dumps(self.server.requests[1][1]))
        self.assertNotIn(SECRET, repr(self.client))

    def test_default_type_and_no_optional_null_fields(self):
        self.client.create_session(action='login', context_id='context_sdk_example_123', origin='https://app.example.com')
        body = self.server.requests[0][1]
        self.assertEqual(body['challenge_type'], 'text')
        self.assertNotIn('rotation_source', body)
        self.assertNotIn('image_set_id', body)

    def test_api_errors_are_typed_and_never_automatically_retried(self):
        self.server.reply = lambda path: (429, FIXTURE['error'])
        with self.assertRaises(StarLockError) as raised:
            self.client.siteverify(token='token.example', action='login', context_id='context_sdk_example_123')
        error = raised.exception
        self.assertEqual((error.code, error.status_code, error.request_id, error.retry_after),
                         ('RATE_LIMITED', 429, 'request_example', 60))
        self.assertNotIn(SECRET, str(error))
        self.assertEqual(len(self.server.requests), 1)

    def test_bad_success_json_and_mismatched_context_are_rejected(self):
        for reply in (b'not json', [], None, {**FIXTURE['verification'], 'success': False},
                      {**FIXTURE['verification'], 'site_key': 'other'},
                      {**FIXTURE['verification'], 'action': 'register'},
                      {**FIXTURE['verification'], 'context_id': 'context_other'}, b' ' * 65537):
            with self.subTest(reply=str(reply)[:80]):
                self.server.reply = lambda path: (200, reply)
                with self.assertRaises(StarLockError) as raised:
                    self.client.siteverify(token='token.example', action='login', context_id='context_sdk_example_123')
                self.assertEqual(raised.exception.code, 'PROTOCOL_ERROR')
        for reply in ({**FIXTURE['session'], 'site_key': 'other'}, {**FIXTURE['session'], 'expires_in': True}):
            self.server.reply = lambda path: (201, reply)
            with self.assertRaises(StarLockError):
                self.client.create_session(action='login', context_id='context_sdk_example_123', origin='https://app.example.com')

    def test_redirects_do_not_forward_credentials(self):
        for status in (301, 302, 303, 307, 308):
            self.server.requests.clear()
            self.server.reply = lambda path: (status, {})
            with self.assertRaises(StarLockError) as raised:
                self.client.create_session(action='login', context_id='context_sdk_example_123', origin='https://app.example.com')
            self.assertEqual(raised.exception.code, 'REDIRECT_DENIED')
            self.assertEqual(len(self.server.requests), 1)

    def test_timeout_returns_an_error_without_retry(self):
        self.server.delay = .1
        client = Client(api_base=self.base, site_key=FIXTURE['site_key'], site_secret=SECRET, timeout=.02)
        with self.assertRaises(StarLockError) as raised:
            client.create_session(action='login', context_id='context_sdk_example_123', origin='https://app.example.com')
        self.assertEqual(raised.exception.code, 'NETWORK_ERROR')
        self.assertEqual(len(self.server.requests), 1)

    def test_configuration_errors_do_not_echo_secret(self):
        for base in ('file:///tmp/example', 'https://user:password@example.com', 'https://example.com?key=x',
                     'https://example.com/#fragment', 'http://[', '', 'https://example.com?', 'https://example.com#', 'https://@example.com'):
            with self.assertRaises(ValueError) as raised:
                Client(api_base=base, site_key=FIXTURE['site_key'], site_secret=SECRET)
            self.assertNotIn(SECRET, str(raised.exception))
        for timeout in (0, -1, True, float('nan')):
            with self.assertRaises(ValueError):
                Client(api_base=self.base, site_key=FIXTURE['site_key'], site_secret=SECRET, timeout=timeout)
