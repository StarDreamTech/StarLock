import base64
import json
import math
import secrets
import tempfile
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from random import Random
from unittest import TestCase
from unittest.mock import ANY, patch

from fastapi.testclient import TestClient
from PIL import Image

from config.settings import Settings
from verification.api import create_app
from verification.errors import VerificationError
from verification.generators import generate
from verification.models import Site, SiteStore
from verification.rotations import PRESETS, generate_rotation, matches_rotation, preset_image
from verification.sliders import (SLIDER_TYPES, SHAPES, PIECE, MIN_TRAVEL, MAX_TRAVEL, angle_distance,
                                  matches_slider, motion_state, path_point, separated, shape_mask, slider_layout)

ORIGIN = "http://127.0.0.1:5178"


class SliderGeneratorTests(TestCase):
    def test_preset_assets_load_and_both_sources_keep_the_same_ring_protocol(self):
        for name in PRESETS:
            image = preset_image(name)
            self.assertEqual(image.size, (256, 256))
            self.assertEqual(image.mode, "RGB")
        preset_images, procedural_images = set(), set()
        for seed in range(12):
            for source, images in (("preset", preset_images), ("procedural", procedural_images)):
                with patch("verification.rotations.SystemRandom", return_value=Random(seed)):
                    payload, solution = generate_rotation(source)
                images.add(payload["image"])
                self.assertEqual(payload["image_width"], 256)
                self.assertEqual(solution["angle_tolerance"], 5)
                self.assertNotIn("source", payload)
                self.assertNotIn("target_angle", payload)
        self.assertEqual(len(preset_images), 12)
        self.assertEqual(len(procedural_images), 12)
        self.assertFalse(preset_images & procedural_images)
        with self.assertRaises(ValueError):
            generate_rotation("../../anything")

    def test_ring_images_are_private_random_and_can_be_aligned_with_easing(self):
        images = set()
        for seed in range(20):
            with patch("verification.rotations.SystemRandom", return_value=Random(seed)):
                payload, solution = generate_rotation()
            self.assertEqual(set(payload), {"instruction", "image", "image_width", "image_height", "piece_image", "piece_width", "piece_height", "motion"})
            outer = Image.open(BytesIO(base64.b64decode(payload["image"].split(",")[1])))
            inner = Image.open(BytesIO(base64.b64decode(payload["piece_image"].split(",")[1])))
            self.assertEqual(outer.size, (256, 256))
            self.assertEqual(outer.mode, "RGBA")
            self.assertEqual(outer.getpixel((128, 128))[3], 0)
            self.assertEqual(inner.getpixel((128, 128))[3], 255)
            self.assertEqual(inner.getpixel((0, 0))[3], 0)
            self.assertTrue(0 < inner.getpixel((210, 128))[3] < 255)
            for radius in range(78, 88):
                for degree in range(0, 360, 10):
                    point = (round(128 + radius * math.cos(math.radians(degree))), round(128 + radius * math.sin(math.radians(degree))))
                    a, b = outer.getpixel(point)[3], inner.getpixel(point)[3]
                    self.assertGreaterEqual(a + b * (1 - a / 255), 245)
            self.assertTrue(75 <= solution["target_angle"] <= 285)
            low, high = 0., 1.
            for _ in range(40):
                middle = (low + high) / 2
                from verification.sliders import eased_progress
                if eased_progress(payload["motion"]["easing"], middle) * 360 < solution["target_angle"]:
                    low = middle
                else:
                    high = middle
            self.assertTrue(matches_rotation(payload, solution, {"progress": (low + high) / 2}))
            self.assertFalse(matches_rotation(payload, solution, {"progress": 0}))
            self.assertFalse(matches_rotation(payload, solution, {"progress": 1}))
            images.add(payload["image"])
        self.assertEqual(len(images), 20)

    def test_ring_angle_uses_css_easing_and_rejects_hostile_input(self):
        payload = {"motion": {"easing": {"kind": "cubic_bezier", "control_points": [{"x": .25, "y": .1}, {"x": .25, "y": 1}]}}}
        solution = {"target_angle": 193.5, "angle_tolerance": 5}
        self.assertTrue(matches_rotation(payload, solution, {"progress": .3125}))
        for answer in ({"progress": .5375}, {"progress": -1}, {"progress": 2}, {"progress": True},
                       {"progress": float("nan")}, {"progress": float("inf")}, {"progress": 10 ** 400},
                       {"progress": "0.3125"}, {"progress": .3125, "angle": 193.5}, {}, "0.3125", None):
            self.assertFalse(matches_rotation(payload, solution, answer))

    def test_random_puzzles_keep_solution_private_and_inside_original_image(self):
        for kind in SLIDER_TYPES:
            images = set()
            for _ in range(12):
                generated = generate(kind)
                payload, solution = generated.payload, generated.solution
                self.assertEqual(set(payload), {"instruction", "image", "image_width", "image_height",
                                               "piece_image", "piece_width", "piece_height", "path", "motion"})
                image = Image.open(BytesIO(base64.b64decode(payload["image"].split(",")[1])))
                piece = Image.open(BytesIO(base64.b64decode(payload["piece_image"].split(",")[1])))
                self.assertEqual(image.size, (320, 180))
                self.assertEqual(piece.size, (PIECE, PIECE))
                self.assertEqual(piece.mode, "RGBA")
                self.assertEqual(piece.getextrema()[3], (0, 255))
                self.assertTrue(8 <= solution["target_x"] <= 248 and 8 <= solution["target_y"] <= 108)
                # Test-only private answer material; no runtime answer endpoint.
                low, high = 0., 1.
                for _ in range(40):
                    middle = (low + high) / 2
                    if motion_state(payload, middle)[0] < solution["target_x"]:
                        low = middle
                    else:
                        high = middle
                progress = (low + high) / 2
                self.assertTrue(matches_slider(payload, solution, {"progress": progress}))
                self.assertFalse(matches_slider(payload, solution, {"progress": 0}))
                images.add(payload["image"])
            self.assertEqual(len(images), 12)

    def test_shared_css_easing_and_rotation_vectors(self):
        fixtures = json.loads((Path(__file__).resolve().parents[3] / "fixtures/slider-motion.json").read_text())
        for fixture in fixtures:
            with self.subTest(fixture["name"]):
                actual = motion_state(fixture["payload"], fixture["progress"])
                for value, key in zip(actual, ("x", "y", "angle")):
                    self.assertAlmostEqual(value, fixture["expected"][key], places=5)

    def test_layout_has_safe_travel_no_overlaps_and_only_one_fitting_hole(self):
        seen_shapes = set()
        for kind in SLIDER_TYPES:
            for seed in range(180):
                layout = slider_layout(kind, Random(seed))
                target = layout["target"]
                seen_shapes.add(target["shape"])
                start = layout["path"]["control_points"][0]
                self.assertTrue(MIN_TRAVEL <= math.hypot(target["x"] - start["x"], target["y"] - start["y"]) <= MAX_TRAVEL)
                self.assertTrue(.35 <= target["progress"] <= .85)
                self.assertIn(len(layout["distractors"]), (1, 2))
                occupied = [start]
                for hole in [target, *layout["distractors"]]:
                    self.assertTrue(8 <= hole["x"] <= 248 and 8 <= hole["y"] <= 108)
                    self.assertTrue(all(separated(hole, old) for old in occupied))
                    occupied.append(hole)
                for n in range(51):
                    x, y, _ = motion_state(layout, n / 50)
                    self.assertTrue(8 - 1e-8 <= x <= 248 + 1e-8 and 8 - 1e-8 <= y <= 108 + 1e-8)
                for hole in layout["distractors"]:
                    if hole["shape"] == target["shape"]:
                        _, _, angle = motion_state(layout, hole["progress"])
                        self.assertGreater(angle_distance(angle, hole["angle"], SHAPES[target["shape"]]), 20)
                        fake_target = {"target_x": hole["x"], "target_y": hole["y"], "tolerance": 4,
                                       "target_angle": hole["angle"], "angle_tolerance": 5, "rotation_period": SHAPES[target["shape"]]}
                        self.assertFalse(matches_slider(layout, fake_target, {"progress": hole["progress"]}))
                    else:
                        self.assertNotEqual(shape_mask(hole["shape"]).tobytes(), shape_mask(target["shape"]).tobytes())
        self.assertEqual(seen_shapes, set(SHAPES))

    def test_rotating_shapes_never_clip_and_angle_is_checked_with_shape_symmetry(self):
        for shape, period in SHAPES.items():
            for angle in range(0, 360, 5):
                left, top, right, bottom = shape_mask(shape, angle).getbbox()
                self.assertTrue(0 < left < right < PIECE and 0 < top < bottom < PIECE, (shape, angle))
            payload = {"path": {"kind": "linear", "control_points": [{"x": 0, "y": 40}, {"x": 200, "y": 40}]},
                       "motion": {"easing": {"kind": "linear"}, "rotation": {"start_degrees": 10, "end_degrees": 10}}}
            solution = {"target_x": 100, "target_y": 40, "tolerance": 4, "target_angle": 10 + period,
                        "angle_tolerance": 5, "rotation_period": period}
            self.assertTrue(matches_slider(payload, solution, {"progress": .5}))
            solution["target_angle"] += 12
            self.assertFalse(matches_slider(payload, solution, {"progress": .5}))

    def test_tolerance_and_hostile_answers(self):
        path = {"kind": "linear", "control_points": [{"x": 0, "y": 40}, {"x": 200, "y": 40}]}
        payload, solution = {"path": path}, {"target_x": 100, "target_y": 40, "tolerance": 4}
        for progress in (.48, .5, .52):
            self.assertTrue(matches_slider(payload, solution, {"progress": progress}))
        for value in ({"progress": .47}, {"progress": .53}, {"progress": float("nan")}, {"progress": float("inf")},
                      {"progress": True}, {"progress": "0.5"}, {"progress": -1}, {"progress": 2},
                      {"progress": 10 ** 400}, {"progress": .5, "target_x": 0}, "0.5", {}, None):
            self.assertFalse(matches_slider(payload, solution, value), value)

    def test_cubic_coordinates_use_both_axes(self):
        path = {"kind": "cubic_bezier", "control_points": [
            {"x": 0, "y": 0}, {"x": 0, "y": 100}, {"x": 100, "y": 100}, {"x": 100, "y": 0}]}
        self.assertEqual(path_point(path, .5), (50, 75))
        self.assertFalse(matches_slider({"path": path}, {"target_x": 50, "target_y": 40, "tolerance": 4}, {"progress": .5}))


class SliderFlowTests(TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.settings = Settings(debug=True, redis_prefix="starlock:test:" + secrets.token_hex(8) + ":",
                                 database_path=Path(directory) / "sites.sqlite3")
        self.store = SiteStore(self.settings.database_path)
        self.store.initialize()
        self.site = Site(key="site_slider", name="Slider", origins=[ORIGIN], actions=["register"])
        self.secret = "ss_" + secrets.token_urlsafe(24)
        self.site.set_secret(self.secret)
        self.store.save(self.site)
        self.client = self.enterContext(TestClient(create_app(self.settings, self.store)))
        self.service = self.client.app.state.service
        self.service.redis.ping()
        self.addCleanup(self.clean)

    def clean(self):
        keys = list(self.service.redis.scan_iter(self.settings.redis_prefix + "*"))
        if keys:
            self.service.redis.delete(*keys)

    def start(self, kind):
        # Deterministic private fixture for HTTP tests, not a runtime answer endpoint.
        self.layout = slider_layout(kind, Random(141))
        self.correct_progress = self.layout["target"]["progress"]
        with patch("verification.sliders.SystemRandom", return_value=Random(141)):
            self.browser = {"site_key": self.site.key, "session_ticket": self.service.create_session(
                self.site, "register", "context_slider_123", ORIGIN, kind)["session_ticket"]}
            self.challenge = self.client.post("/v1/challenges", json=self.browser, headers={"Origin": ORIGIN}).json()
        self.url = f'/v1/challenges/{self.challenge["challenge_id"]}/verify'
        return self.challenge

    def verify(self, answer):
        return self.client.post(self.url, json={**self.browser, "answer": answer}, headers={"Origin": ORIGIN})

    def test_rotation_source_is_validated_and_bound_to_the_backend_session(self):
        body = {"site_key": self.site.key, "action": "register", "context_id": "context_source_123",
                "origin": ORIGIN, "challenge_type": "rotate"}
        auth = {"Authorization": "Bearer " + self.secret}
        for source in (None, "preset", "procedural"):
            result = self.client.post("/v1/sessions", json={**body, **({"rotation_source": source} if source else {})}, headers=auth)
            self.assertEqual(result.status_code, 201, result.text)
            browser = {"site_key": self.site.key, "session_ticket": result.json()["session_ticket"]}
            headers = {"Origin": ORIGIN}
            with patch("verification.service.generate", wraps=generate) as generator:
                first = self.client.post("/v1/challenges", json=browser, headers=headers)
                self.assertEqual(first.status_code, 200, first.text)
                generator.assert_called_once_with("rotate", rotation_source=source or "preset", **({"image": ANY} if source != "procedural" else {}))
                tampered = self.client.post("/v1/challenges", json={**browser, "rotation_source": "procedural"}, headers=headers)
                self.assertEqual(tampered.status_code, 400)
                generator.reset_mock()
                refreshed = self.client.post("/v1/challenges", json={**browser, "replace_challenge_id": first.json()["challenge_id"]}, headers=headers)
                self.assertEqual(refreshed.status_code, 200, refreshed.text)
                generator.assert_called_once_with("rotate", rotation_source=source or "preset", **({"image": ANY} if source != "procedural" else {}))
        for extra in ({"rotation_source": "external"}, {"challenge_type": "digits", "rotation_source": "preset"}):
            self.assertEqual(self.client.post("/v1/sessions", json={**body, **extra}, headers=auth).status_code, 400)

    def test_ring_challenge_attempts_and_one_time_token_flow(self):
        from verification.sliders import eased_progress
        with patch("verification.rotations.SystemRandom", return_value=Random(17)):
            generated = generate("rotate")
        self.browser = {"site_key": self.site.key, "session_ticket": self.service.create_session(
            self.site, "register", "context_slider_123", ORIGIN, "rotate")["session_ticket"]}
        with patch("verification.service.generate", return_value=generated):
            challenge = self.client.post("/v1/challenges", json=self.browser, headers={"Origin": ORIGIN}).json()
        self.assertEqual(challenge["challenge_type"], "rotate")
        self.assertNotIn("target_angle", json.dumps(challenge))
        self.url = f'/v1/challenges/{challenge["challenge_id"]}/verify'
        self.assertEqual(self.verify({"progress": 0}).json()["attempts_remaining"], 2)
        low, high = 0., 1.
        for _ in range(40):
            u = (low + high) / 2
            if eased_progress(generated.payload["motion"]["easing"], u) * 360 < generated.solution["target_angle"]:
                low = u
            else:
                high = u
        token = self.verify({"progress": (low + high) / 2})
        self.assertEqual(token.status_code, 200, token.text)
        body = {"site_key": self.site.key, "token": token.json()["verification_token"], "action": "register", "context_id": "context_slider_123"}
        result = self.client.post("/v1/siteverify", headers={"Authorization": "Bearer " + self.secret}, json=body)
        self.assertEqual(result.json()["challenge_type"], "rotate")
        self.assertEqual(self.client.post("/v1/siteverify", headers={"Authorization": "Bearer " + self.secret}, json=body).json()["error_code"], "TOKEN_USED")

    def test_both_slider_types_complete_existing_token_flow_without_target_leak(self):
        for kind in SLIDER_TYPES:
            with self.subTest(kind=kind):
                challenge = self.start(kind)
                self.assertEqual(challenge["challenge_type"], kind)
                self.assertFalse({"solution", "answer", "target_x", "target_y", "target_angle", "angle_tolerance",
                                  "distractors", "tolerance", "progress"} & challenge["payload"].keys())
                token = self.verify({"progress": self.correct_progress})
                self.assertEqual(token.status_code, 200, token.text)
                result = self.client.post("/v1/siteverify", headers={"Authorization": "Bearer " + self.secret}, json={
                    "site_key": self.site.key, "token": token.json()["verification_token"], "action": "register", "context_id": "context_slider_123"})
                self.assertEqual(result.status_code, 200, result.text)
                self.assertEqual(result.json()["challenge_type"], kind)
                self.assertEqual(self.verify({"progress": self.correct_progress}).json()["error_code"], "SESSION_CLOSED")

    def test_wrong_answers_count_and_refresh_replaces_puzzle(self):
        self.start("slider")
        for remaining in (2, 1, 0):
            result = self.verify({"progress": 0})
            self.assertEqual(result.json()["attempts_remaining"], remaining)
        self.assertEqual(self.verify({"progress": .62}).json()["error_code"], "ATTEMPTS_EXCEEDED")
        new = self.client.post("/v1/challenges", json={**self.browser, "replace_challenge_id": self.challenge["challenge_id"]}, headers={"Origin": ORIGIN})
        self.assertEqual(new.status_code, 200)
        self.assertNotEqual(new.json()["challenge_id"], self.challenge["challenge_id"])
        self.assertNotEqual(new.json()["payload"]["image"], self.challenge["payload"]["image"])
        self.assertEqual(self.verify({"progress": .62}).json()["error_code"], "CHALLENGE_REPLACED")

    def test_http_rejects_unbounded_values_and_client_target_override(self):
        self.start("bezier_slider")
        for answer in ({"progress": -1}, {"progress": 1.1}, {"progress": "0.62"}, {"progress": True},
                       {"progress": .62, "target_x": 0}, {"progress": .62, "path": {}}, {"progress": .62, "angle": 0},
                       {"progress": .62, "motion": {}}, {"progress": None}, {}):
            self.assertEqual(self.verify(answer).status_code, 400, answer)
        self.assertEqual(self.verify("0.62").json()["error_code"], "ANSWER_INVALID")

    def test_distractor_position_fails_then_correct_position_and_rotation_pass(self):
        self.start("slider")
        distractor = self.layout["distractors"][0]
        self.assertEqual(self.verify({"progress": distractor["progress"]}).json()["error_code"], "ANSWER_INVALID")
        self.assertEqual(self.verify({"progress": self.correct_progress}).status_code, 200)

    def test_site_types_are_not_silently_upgraded(self):
        self.site.challenge_types = ["text"]
        self.store.save(self.site)
        self.store.initialize()
        self.assertEqual(self.store.get(self.site.key).challenge_types, ["text"])
        response = self.client.post("/v1/sessions", headers={"Authorization": "Bearer " + self.secret}, json={
            "site_key": self.site.key, "action": "register", "context_id": "context_slider_123", "origin": ORIGIN, "challenge_type": "slider"})
        self.assertEqual(response.json()["error_code"], "TYPE_DENIED")

    def test_concurrent_slider_answers_issue_only_one_token(self):
        self.start("bezier_slider")
        def attempt(_):
            try:
                self.service.verify(self.browser["session_ticket"], self.site.key, ORIGIN, self.challenge["challenge_id"], {"progress": self.correct_progress})
                return "passed"
            except VerificationError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(attempt, range(6)))
        self.assertEqual(results.count("passed"), 1)
        self.assertEqual(results.count("SESSION_CLOSED"), 5)
