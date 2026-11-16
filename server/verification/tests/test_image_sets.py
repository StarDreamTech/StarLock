import json
import secrets
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from config.settings import Settings
from verification.api import create_app
from verification.errors import VerificationError
from verification.image_sets import ImageSetStore, MAX_UPLOAD_BYTES, normalize_upload
from verification.models import Site, SiteStore
from verification.sliders import eased_progress, motion_state

ADMIN = 'http://testserver'
ORIGIN = 'http://127.0.0.1:5178'
TOKEN = 'test-admin-only-' + 'a' * 32


def artwork(size=(420, 360), color='#8262b3'):
    image = Image.new('RGB', size, '#eee5fa')
    draw = ImageDraw.Draw(image)
    draw.rectangle((size[0] * .15, size[1] * .08, size[0] * .75, size[1] * .92), fill=color)
    draw.ellipse((size[0] * .05, size[1] * .2, size[0] * .45, size[1] * .7), fill='#e8ae82')
    stream = BytesIO()
    image.save(stream, 'PNG')
    return stream.getvalue()


class ImageSetTests(TestCase):
    def setUp(self):
        self.directory = self.enterContext(tempfile.TemporaryDirectory())
        self.sites = SiteStore(Path(self.directory) / 'images.sqlite3')
        self.sites.initialize()
        self.images = ImageSetStore(self.sites)
        self.images.initialize()

    def custom(self):
        sid = self.images.create('自有品牌')['id']
        aid = self.images.upload(sid, 'my-image.png', artwork())['id']
        self.images.update(sid, '自有品牌', True)
        return sid, aid

    def test_twenty_new_and_three_existing_system_assets_are_distinct_and_persistent(self):
        sets = self.images.list()
        self.assertEqual(sum(s['image_count'] for s in sets['sets']), 23)
        self.assertEqual(len(self.images.system), 23)
        hashes = set()
        for item in self.images.system.values():
            import hashlib
            sha = hashlib.sha256(item['path'].read_bytes()).hexdigest()
            hashes.add(sha)
            if 'sha256' in item:
                self.assertEqual(sha, item['sha256'])
            self.assertGreaterEqual(min(self.images.image(item['id']).size), 256)
        self.assertEqual(len(hashes), 23)
        self.images.update('system-orbit', '我的星际', False)
        self.images.initialize()
        self.assertEqual(self.images.detail('system-orbit')['name'], '我的星际')
        self.assertEqual(self.images.detail('system-orbit')['active'], 0)

    def test_default_selection_and_disabling_guard_are_transactional(self):
        sid, aid = self.custom()
        self.images.set_default(sid)
        for change in (lambda: self.images.update(sid, 'bad', False), lambda: self.images.set_image_active(aid, False)):
            with self.assertRaises(VerificationError) as result:
                change()
            self.assertEqual(result.exception.code, 'DEFAULT_SET_EMPTY')
        self.assertEqual(self.images.detail(sid)['name'], '自有品牌')
        self.assertEqual(self.images.detail(sid)['images'][0]['active'], 1)
        self.images.set_default('system-all')
        self.images.set_image_active(aid, False)
        with self.assertRaises(VerificationError):
            self.images.resolve(sid)
        with self.sites.connect() as db:
            self.assertNotIn(aid, [r[0] for r in self.images.available(db, 'system-all')])

    def test_upload_deduplicates_even_when_concurrent_and_survives_restart(self):
        sid = self.images.create('上传图库')['id']
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda n: self.images.upload(sid, str(n), artwork()), range(4)))
        self.assertEqual(sum(not r['duplicate'] for r in results), 1)
        self.assertEqual(len({r['id'] for r in results}), 1)
        fresh = ImageSetStore(self.sites)
        self.assertEqual(len(fresh.detail(sid)['images']), 1)
        self.assertEqual(fresh.image(results[0]['id']).size, (420, 360))
        with self.assertRaises(VerificationError) as result:
            self.images.upload('system-orbit', 'disallowed', artwork())
        self.assertEqual(result.exception.code, 'SYSTEM_SET_READONLY')

    def test_invalid_animated_oversized_plain_and_small_images_rejected(self):
        plain = BytesIO(); Image.new('RGB', (256, 256), 'white').save(plain, 'PNG')
        animated = BytesIO(); Image.new('RGB', (256, 256), 'red').save(animated, 'PNG', save_all=True, append_images=[Image.new('RGB', (256, 256), 'blue')], duration=100, loop=0)
        for raw in (b'bad-data', b'<svg/>', b'x' * (MAX_UPLOAD_BYTES + 1), artwork((100, 100)), plain.getvalue(), animated.getvalue()):
            with self.subTest(length=len(raw)), self.assertRaises(VerificationError):
                normalize_upload(raw)
        image = Image.open(BytesIO(artwork()))
        jpeg = BytesIO(); image.save(jpeg, 'JPEG', exif=b'Exif\x00\x00private')
        data, w, h = normalize_upload(jpeg.getvalue())
        with Image.open(BytesIO(data)) as cleaned:
            self.assertEqual(cleaned.mode, 'RGB')
            self.assertNotIn('exif', cleaned.info)
            self.assertEqual(cleaned.size, (w, h))


class ImageAdminTests(TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.settings = Settings(debug=True, demo_enabled=True, admin_token=TOKEN,
                                 redis_prefix='starlock:test:' + secrets.token_hex(8) + ':', database_path=Path(directory) / 'db.sqlite3')
        self.client = self.enterContext(TestClient(create_app(self.settings)))
        self.service = self.client.app.state.service
        self.service.redis.ping()
        self.addCleanup(self.clean)

    def clean(self):
        keys = list(self.service.redis.scan_iter(self.settings.redis_prefix + '*'))
        if keys:
            self.service.redis.delete(*keys)

    def post(self, path, data):
        return self.client.post('/admin/api' + path, json=data, headers={'Origin': ADMIN})

    def login(self):
        response = self.post('/login', {'token': TOKEN})
        self.assertEqual(response.status_code, 200, response.text)
        return response

    def custom(self):
        self.login()
        created = self.post('/sets', {'name': '专属图片集'})
        self.assertEqual(created.status_code, 201)
        sid = created.json()['id']
        result = self.client.post('/admin/api/sets/' + sid + '/images', content=artwork(),
                                  headers={'Origin': ADMIN, 'Content-Type': 'image/png', 'X-File-Name': '%E6%98%9F%E9%94%81.png'})
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(self.post('/sets/' + sid, {'name': '专属图片集', 'active': True}).status_code, 200)
        return sid, result.json()['id']

    def test_auth_origin_private_preview_and_logout(self):
        self.assertEqual(self.client.get('/admin/api/sets').status_code, 401)
        self.assertEqual(self.post('/login', {'token': '错口令'}).status_code, 403)
        self.assertEqual(self.client.post('/admin/api/login', json={'token': TOKEN}, headers={'Origin': 'https://evil.invalid'}).status_code, 403)
        response = self.login()
        self.assertIn('HttpOnly', response.headers['set-cookie'])
        self.assertIn('SameSite=strict', response.headers['set-cookie'])
        for headers in ({}, {'Origin': 'https://evil.invalid'}):
            self.assertEqual(self.client.post('/admin/api/sets', json={'name': 'CSRF'}, headers=headers).status_code, 403)
        public = self.client.get('/admin')
        self.assertIn("frame-ancestors 'none'", public.headers['content-security-policy'])
        self.assertEqual(public.headers['x-robots-tag'], 'noindex, nofollow')
        thumb = self.client.get('/admin/api/images/01-lunar-observatory/preview')
        self.assertEqual(thumb.status_code, 200)
        self.assertEqual(Image.open(BytesIO(thumb.content)).size, (320, 320))
        self.assertNotIn('data', self.client.get('/admin/api/sets/system-orbit').json()['images'][0])
        self.assertEqual(self.post('/logout', {}).status_code, 200)
        self.assertEqual(self.client.get('/admin/api/images/01-lunar-observatory/preview').status_code, 401)

    def test_local_mode_requires_debug_demo_loopback_and_origin(self):
        settings = replace(self.settings, admin_token='')
        app = create_app(settings)
        with TestClient(app, client=('127.0.0.1', 1234)) as local:
            self.assertTrue(local.get('/admin/api/status').json()['local_mode'])
            self.assertEqual(local.post('/admin/api/login', json={}).status_code, 403)
            self.assertEqual(local.post('/admin/api/login', json={}, headers={'Origin': ADMIN}).status_code, 200)
        with TestClient(app, client=('203.0.113.1', 1234)) as remote:
            self.assertFalse(remote.get('/admin/api/status').json()['enabled'])
            self.assertEqual(remote.post('/admin/api/login', json={}, headers={'Origin': ADMIN}).status_code, 503)

    def test_upload_bounded_content_and_normalization(self):
        sid, aid = self.custom()
        url = '/admin/api/sets/' + sid + '/images'
        for raw, ctype, status in ((b'<svg/>', 'image/svg+xml', 415), (b'broken', 'image/png', 400), (b'x' * (MAX_UPLOAD_BYTES + 1), 'image/png', 413)):
            response = self.client.post(url, content=raw, headers={'Origin': ADMIN, 'Content-Type': ctype})
            self.assertEqual(response.status_code, status, response.text)
        def chunks():
            for _ in range(6):
                yield b'x' * 1024 * 1024
        self.assertEqual(self.client.post(url, content=chunks(), headers={'Origin': ADMIN, 'Content-Type': 'image/png'}).status_code, 413)
        self.assertEqual(self.client.post('/v1/sessions', content=b'{}', headers={'Content-Type': 'image/png'}).status_code, 415)
        self.assertEqual(self.client.post('/admin/api/sets', json={'name': 'x' * 40000}, headers={'Origin': ADMIN}).status_code, 413)
        self.assertEqual(self.client.get('/admin/api/sets/' + sid).json()['images'][0]['name'], '星锁.png')
        self.assertEqual(self.client.get('/admin/api/images/' + aid + '/preview').status_code, 200)

    def test_collection_is_bound_and_refresh_checks_enabled_images_without_leaking_source(self):
        sid, aid = self.custom()
        self.post('/default', {'set_id': sid})
        site = Site(name='Image tests', key='site_images', origins=[ORIGIN], actions=['register'])
        self.service.sites.save(site)
        browser = {'site_key': site.key, 'session_ticket': self.service.create_session(site, 'register', 'image_context_123', ORIGIN, 'rotate')['session_ticket']}
        state = json.loads(self.service.redis.get(self.service.key(browser['session_ticket'].split('.')[0])))
        self.assertEqual(state['image_set_id'], sid)
        self.post('/default', {'set_id': 'system-all'})
        sample = self.service.image_sets.sample
        with patch.object(self.service.image_sets, 'sample', wraps=sample) as sampling:
            first = self.client.post('/v1/challenges', json=browser, headers={'Origin': ORIGIN})
            self.assertEqual(first.status_code, 200, first.text)
            sampling.assert_called_once_with(sid)
        self.assertNotIn(aid, first.text); self.assertNotIn(sid, first.text); self.assertNotIn('target_angle', first.text)
        self.assertEqual(self.client.post('/v1/challenges', json={**browser, 'image_set_id': 'system-orbit'}, headers={'Origin': ORIGIN}).status_code, 400)
        self.service.image_sets.set_image_active(aid, False)
        cached = self.client.post('/v1/challenges', json=browser, headers={'Origin': ORIGIN})
        self.assertEqual(cached.json()['challenge_id'], first.json()['challenge_id'])
        refresh = self.client.post('/v1/challenges', json={**browser, 'replace_challenge_id': first.json()['challenge_id']}, headers={'Origin': ORIGIN})
        self.assertEqual(refresh.json()['error_code'], 'IMAGE_SET_UNAVAILABLE')
        self.service.image_sets.set_image_active(aid, True)
        self.assertEqual(self.client.post('/v1/challenges', json={**browser, 'replace_challenge_id': first.json()['challenge_id']}, headers={'Origin': ORIGIN}).status_code, 200)
        for kind, source in (('digits', None), ('rotate', 'procedural')):
            with self.assertRaises(VerificationError):
                self.service.create_session(site, 'register', 'image_context_123', ORIGIN, kind, source, sid)

    def test_custom_images_work_for_all_visual_types_and_complete_token_flow(self):
        sid, _ = self.custom()
        site = Site(name='Image tests', key='site_flow', origins=[ORIGIN], actions=['register'])
        self.service.sites.save(site)
        for kind in ('rotate', 'slider', 'bezier_slider'):
            ticket = self.service.create_session(site, 'register', 'image_context_123', ORIGIN, kind, image_set_id=sid)['session_ticket']
            public = self.service.challenge(ticket, site.key, ORIGIN)
            state = json.loads(self.service.redis.get(self.service.key(ticket.split('.')[0])))
            private = state['challenge']
            if kind == 'rotate':
                low, high = 0., 1.
                for _ in range(40):
                    u = (low + high) / 2
                    if eased_progress(private['payload']['motion']['easing'], u) * 360 < private['solution']['target_angle']:
                        low = u
                    else:
                        high = u
            else:
                low, high = 0., 1.
                for _ in range(40):
                    u = (low + high) / 2
                    if motion_state(private['payload'], u)[0] < private['solution']['target_x']:
                        low = u
                    else:
                        high = u
            result = self.service.verify(ticket, site.key, ORIGIN, public['challenge_id'], {'progress': (low + high) / 2})
            self.assertTrue(self.service.consume(site, result['verification_token'], 'register', 'image_context_123')['success'])
            with self.assertRaises(VerificationError):
                self.service.consume(site, result['verification_token'], 'register', 'image_context_123')
