import base64
import json
import secrets
import tempfile
from collections import Counter
from io import BytesIO
from pathlib import Path
from random import Random
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from config.settings import Settings
from verification.api import create_app
from verification.generators import generate
from verification.models import Site, SiteStore
from verification.selections import (SEMANTIC_QUESTIONS, matches_semantic_grid, matches_text_click,
                                     semantic_catalog, semantic_tile)

ORIGIN = 'http://127.0.0.1:5178'


class SelectionGeneratorTests(TestCase):
    def test_ordered_clicks_have_private_nonoverlapping_targets_and_small_images(self):
        for _ in range(12):
            generated = generate('text_click')
            payload, solution = generated.payload, generated.solution
            self.assertEqual(set(payload), {'instruction', 'image', 'image_width', 'image_height', 'required_clicks'})
            self.assertEqual(payload['required_clicks'], 3)
            data = base64.b64decode(payload['image'].split(',')[1])
            self.assertLess(len(data), 100_000)
            self.assertEqual(Image.open(BytesIO(data)).size, (300, 180))
            points = solution['targets']
            self.assertEqual(len({tuple(point.values()) for point in points}), 3)
            self.assertTrue(all(.1 < point['x'] < .9 and .1 < point['y'] < .9 for point in points))
            self.assertTrue(matches_text_click(payload, solution, {'points': points}))
            self.assertFalse(matches_text_click(payload, solution, {'points': points[::-1]}))
            shifted = [{**point, 'x': point['x'] + .05} for point in points]
            self.assertTrue(matches_text_click(payload, solution, {'points': shifted}))
            shifted[0]['x'] += .1
            self.assertFalse(matches_text_click(payload, solution, {'points': shifted}))
            for invalid in ({'points': points[:2]}, {'points': points * 2}, {'points': [points[0]] * 3},
                            {'points': points, 'answer': 'extra'}, {'points': [{'x': True, 'y': .5}] * 3},
                            {'points': [{'x': float('nan'), 'y': .5}] * 3}, {'points': [{'x': 2, 'y': .5}] * 3},
                            {'points': [{'x': '0.5', 'y': .5}] * 3}, {'points': [None] * 3}, '星月山', None):
                self.assertFalse(matches_text_click(payload, solution, invalid), invalid)

    def test_semantic_catalog_is_labeled_small_and_every_category_can_fill_a_grid(self):
        catalog = semantic_catalog()
        self.assertEqual(Counter(item['category'] for item in catalog), {'car': 4, 'boat': 4, 'fruit': 4})
        for item in catalog:
            path = Path(__file__).resolve().parents[2] / 'assets/semantic' / item['file']
            self.assertLess(path.stat().st_size, 300_000)
            data = base64.b64decode(semantic_tile(item['file']).split(',')[1])
            self.assertLess(len(data), 20_000)
            self.assertEqual(Image.open(BytesIO(data)).size, (192, 192))
        seen = set()
        for seed in range(30):
            with patch('verification.selections.SystemRandom', return_value=Random(seed)):
                generated = generate('semantic_grid')
            payload, solution = generated.payload, generated.solution
            self.assertEqual(set(payload), {'instruction', 'columns', 'tiles'})
            self.assertEqual(payload['columns'], 3)
            self.assertEqual(len(payload['tiles']), 9)
            self.assertEqual(len({tile['id'] for tile in payload['tiles']}), 9)
            self.assertEqual(len({tile['image'] for tile in payload['tiles']}), 9)
            expected = solution['tile_ids']
            self.assertTrue(2 <= len(expected) <= 4)
            question_category = next(category for category, questions in SEMANTIC_QUESTIONS.items()
                                     if payload['instruction'] in questions)
            seen.add(question_category)
            image_categories = {semantic_tile(item['file']): item['category'] for item in catalog}
            self.assertEqual(set(expected), {tile['id'] for tile in payload['tiles']
                                            if image_categories[tile['image']] == question_category})
            self.assertTrue(matches_semantic_grid(payload, solution, {'tile_ids': expected[::-1]}))
            self.assertTrue(all(set(tile) == {'id', 'image'} for tile in payload['tiles']))
            for invalid in ({'tile_ids': expected[:1]}, {'tile_ids': expected + expected},
                            {'tile_ids': [tile['id'] for tile in payload['tiles']]},
                            {'tile_ids': ['unknown']}, {'tile_ids': []}, {'tile_ids': [True]},
                            {'tile_ids': expected, 'category': question_category}, None):
                self.assertFalse(matches_semantic_grid(payload, solution, invalid))
        self.assertEqual(seen, set(SEMANTIC_QUESTIONS))


class SelectionFlowTests(TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.settings = Settings(debug=True, database_path=Path(directory) / 'sites.sqlite3',
                                 redis_prefix='starlock:test:' + secrets.token_hex(8) + ':')
        self.store = SiteStore(self.settings.database_path)
        self.store.initialize()
        self.site = Site(key='site_selections', name='Selections', origins=[ORIGIN], actions=['register'])
        self.secret = 'ss_' + secrets.token_urlsafe(24)
        self.site.set_secret(self.secret)
        self.store.save(self.site)
        self.client = self.enterContext(TestClient(create_app(self.settings, self.store)))
        self.service = self.client.app.state.service
        self.service.redis.ping()
        self.addCleanup(self.clean)

    def clean(self):
        keys = list(self.service.redis.scan_iter(self.settings.redis_prefix + '*'))
        if keys:
            self.service.redis.delete(*keys)

    def start(self, kind):
        response = self.client.post('/v1/sessions', json={'site_key': self.site.key, 'origin': ORIGIN,
            'action': 'register', 'context_id': 'context_selections_123', 'challenge_type': kind},
            headers={'Authorization': 'Bearer ' + self.secret})
        self.assertEqual(response.status_code, 201, response.text)
        browser = {'site_key': self.site.key, 'session_ticket': response.json()['session_ticket']}
        generated = generate(kind)
        with patch('verification.service.generate', return_value=generated):
            challenge = self.client.post('/v1/challenges', json=browser, headers={'Origin': ORIGIN})
        self.assertEqual(challenge.status_code, 200, challenge.text)
        answer = {'points': generated.solution['targets']} if kind == 'text_click' else generated.solution
        return browser, challenge.json(), answer

    def test_both_types_retry_refresh_and_issue_one_time_verified_tokens(self):
        for kind in ('text_click', 'semantic_grid'):
            with self.subTest(kind=kind):
                browser, challenge, answer = self.start(kind)
                self.assertNotIn('solution', challenge)
                path = f'/v1/challenges/{challenge["challenge_id"]}/verify'
                wrong = {'points': [{'x': 0, 'y': 0}] * 3} if kind == 'text_click' else {'tile_ids': [challenge['payload']['tiles'][0]['id']]}
                result = self.client.post(path, json={**browser, 'answer': wrong}, headers={'Origin': ORIGIN})
                self.assertEqual(result.status_code, 400, result.text)
                self.assertEqual(result.json()['attempts_remaining'], 2)
                result = self.client.post(path, json={**browser, 'answer': answer}, headers={'Origin': ORIGIN})
                self.assertEqual(result.status_code, 200, result.text)
                token = result.json()['verification_token']
                self.assertTrue(self.service.consume(self.site, token, 'register', 'context_selections_123')['success'])
                replay = self.client.post('/v1/siteverify', json={'site_key': self.site.key, 'token': token,
                    'action': 'register', 'context_id': 'context_selections_123'}, headers={'Authorization': 'Bearer ' + self.secret})
                self.assertEqual(replay.json()['error_code'], 'TOKEN_USED')
                browser, challenge, answer = self.start(kind)
                fresh = self.client.post('/v1/challenges', json={**browser, 'replace_challenge_id': challenge['challenge_id']}, headers={'Origin': ORIGIN})
                self.assertNotEqual(fresh.json()['challenge_id'], challenge['challenge_id'])
                old = self.client.post(f'/v1/challenges/{challenge["challenge_id"]}/verify', json={**browser, 'answer': answer}, headers={'Origin': ORIGIN})
                self.assertEqual(old.json()['error_code'], 'CHALLENGE_REPLACED')

    def test_http_rejects_malformed_choices_and_keeps_existing_site_permissions(self):
        browser, challenge, _ = self.start('text_click')
        path = f'/v1/challenges/{challenge["challenge_id"]}/verify'
        for answer in ({'points': [{'x': 2, 'y': .5}]}, {'tile_ids': [1]}, {'points': []},
                       {'points': [{'x': .5, 'y': .5, 'extra': 1}]}):
            response = self.client.post(path, json={**browser, 'answer': answer}, headers={'Origin': ORIGIN})
            self.assertEqual(response.status_code, 400, response.text)
        self.site.challenge_types = ['digits']
        self.store.save(self.site)
        response = self.client.post('/v1/sessions', json={'site_key': self.site.key, 'origin': ORIGIN,
            'action': 'register', 'context_id': 'context_selections_123', 'challenge_type': 'semantic_grid'},
            headers={'Authorization': 'Bearer ' + self.secret})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.store.get(self.site.key).challenge_types, ['digits'])
