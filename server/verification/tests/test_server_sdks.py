import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, skipUnless
from unittest.mock import patch
from urllib.request import Request, urlopen

import uvicorn
from config.settings import Settings
from verification.api import create_app
from verification.generators import TYPES, generate
from verification.models import Site, SiteStore

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'sdks/python/src'))
from starlock import Client, StarLockError


class ServerSDKFlows(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.settings = Settings(debug=True, redis_prefix='starlock:test:' + secrets.token_hex(8) + ':',
                                database_path=Path(cls.directory.name) / 'sites.sqlite3')
        store = SiteStore(cls.settings.database_path)
        store.initialize()
        cls.site = Site(key='site_sdk_test', name='SDK integration', actions=['login'], origins=['https://app.example.com'])
        cls.secret = 'ss_' + secrets.token_urlsafe(32)
        cls.site.set_secret(cls.secret)
        store.save(cls.site)
        cls.app = create_app(cls.settings, store)
        cls.listener = socket.create_server(('127.0.0.1', 0))
        cls.addClassCleanup(cls.listener.close)
        cls.base = f'http://127.0.0.1:{cls.listener.getsockname()[1]}'
        cls.server = uvicorn.Server(uvicorn.Config(cls.app, log_level='critical', timeout_graceful_shutdown=1))
        cls.thread = threading.Thread(target=cls.server.run, kwargs={'sockets': [cls.listener]}, daemon=True)
        cls.addClassCleanup(cls.stop)
        cls.thread.start()
        deadline = time.monotonic() + 5
        while not cls.server.started and cls.thread.is_alive() and time.monotonic() < deadline:
            time.sleep(.01)
        if not cls.server.started:
            raise RuntimeError('Isolated SDK integration API failed to start')

    @classmethod
    def stop(cls):
        cls.server.should_exit = True
        cls.thread.join(5)
        keys = list(cls.app.state.service.redis.scan_iter(cls.settings.redis_prefix + '*'))
        if keys:
            cls.app.state.service.redis.delete(*keys)

    def setUp(self):
        # A private fixture belongs only to this isolated test API.
        self.enterContext(patch('verification.service.generate', return_value=replace(generate('text'), answer='ABCDE')))

    def test_python_sessions_all_types_and_one_time_backend_verification(self):
        client = Client(api_base=self.base, site_key=self.site.key, site_secret=self.secret)
        for kind in TYPES:
            session = client.create_session(action='login', context_id='context_python_types_123',
                                            origin='https://app.example.com', challenge_type=kind)
            self.assertEqual(session.site_key, self.site.key)
        session = client.create_session(action='login', context_id='context_python_flow_123', origin='https://app.example.com')
        browser = {'site_key': session.site_key, 'session_ticket': session.session_ticket}

        def post(path, body):
            request = Request(self.base + path, method='POST', data=json.dumps(body).encode(),
                              headers={'Content-Type': 'application/json', 'Origin': 'https://app.example.com'})
            with urlopen(request, timeout=5) as response:
                return json.load(response)
        challenge = post('/v1/challenges', browser)
        token = post(f'/v1/challenges/{challenge["challenge_id"]}/verify', {**browser, 'answer': 'ABCDE'})['verification_token']
        with self.assertRaises(StarLockError) as raised:
            client.siteverify(token=token, action='login', context_id='context_wrong_123')
        self.assertEqual(raised.exception.code, 'CONTEXT_MISMATCH')
        result = client.siteverify(token=token, action='login', context_id='context_python_flow_123')
        self.assertTrue(result.success)
        with self.assertRaises(StarLockError) as raised:
            client.siteverify(token=token, action='login', context_id='context_python_flow_123')
        self.assertEqual(raised.exception.code, 'TOKEN_USED')

    @skipUnless(shutil.which('go'), 'Go is required only for the cross-language SDK integration test')
    def test_go_sessions_all_types_and_one_time_backend_verification(self):
        result = subprocess.run(['go', 'test', '-run', '^TestLiveAPI$', '-count=1', '-timeout=30s', '-v'],
            cwd=ROOT / 'sdks/go', env={**os.environ, 'STARLOCK_TEST_API_BASE': self.base,
                'STARLOCK_TEST_SITE_KEY': self.site.key, 'STARLOCK_TEST_SITE_SECRET': self.secret},
            text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('--- PASS: TestLiveAPI', result.stdout)
