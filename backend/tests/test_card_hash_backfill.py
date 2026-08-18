"""Tests for the card-hash backfill service and its admin API endpoints.

Covers the running guard (so scheduler ticks and manual UI triggers can't
race each other), the incremental vs --force card selection, the coverage
counts shown in Settings, and the three admin-only endpoints.
"""
import threading
import unittest
from unittest.mock import MagicMock, patch

try:
    import cv2
    import numpy as np
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from api.auth import get_current_user
    from api.card_hashes import router
    from database import Base, get_db
    from models import Card, CardHash, User
    from services import card_hash_backfill

    DEPS_AVAILABLE = True
except ModuleNotFoundError:
    DEPS_AVAILABLE = False


def _synthetic_card_photo_bytes() -> bytes:
    corners = [(220, 90), (710, 130), (680, 690), (190, 660)]
    canvas = np.full((800, 900, 3), 230, dtype=np.uint8)
    cv2.fillConvexPoly(canvas, np.array(corners, dtype=np.int32), (40, 120, 200))
    ok, buf = cv2.imencode(".png", canvas)
    assert ok
    return buf.tobytes()


def _fake_httpx_client(image_bytes: bytes, *, status_code: int = 200):
    response = MagicMock()
    response.content = image_bytes
    response.raise_for_status = MagicMock() if status_code == 200 else MagicMock(
        side_effect=Exception(f"HTTP {status_code}")
    )
    client = MagicMock()
    client.get = MagicMock(return_value=response)
    context_manager = MagicMock()
    context_manager.__enter__ = MagicMock(return_value=client)
    context_manager.__exit__ = MagicMock(return_value=False)
    return context_manager


@unittest.skipUnless(DEPS_AVAILABLE, "opencv/imagehash/SQLAlchemy are not installed")
class HashCoverageCountsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.session_patch = patch.object(card_hash_backfill, "SessionLocal", self.Session)
        self.session_patch.start()

    def tearDown(self):
        self.session_patch.stop()
        self.db.close()

    def _add_card(self, card_id, *, is_custom=False, is_digital=False, has_image=True):
        self.db.add(
            Card(
                id=card_id,
                tcg_card_id=card_id,
                name="Test",
                set_id="s1",
                number="1",
                lang="en",
                is_custom=is_custom,
                is_digital=is_digital,
                images_large=f"https://example.test/{card_id}.png" if has_image else None,
            )
        )

    def test_counts_exclude_custom_digital_and_imageless_cards(self):
        self._add_card("a")
        self._add_card("b", is_custom=True)
        self._add_card("c", is_digital=True)
        self._add_card("d", has_image=False)
        self.db.commit()

        counts = card_hash_backfill.hash_coverage_counts()
        self.assertEqual(counts, {"total_hashable": 1, "hashed": 0, "missing": 1})

    def test_hashed_card_reduces_missing_count(self):
        self._add_card("a")
        self._add_card("b")
        self.db.add(CardHash(card_id="a", phash="0", dhash="0", whash="0"))
        self.db.commit()

        counts = card_hash_backfill.hash_coverage_counts()
        self.assertEqual(counts, {"total_hashable": 2, "hashed": 1, "missing": 1})


@unittest.skipUnless(DEPS_AVAILABLE, "opencv/imagehash/SQLAlchemy are not installed")
class RunBackfillTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.session_patch = patch.object(card_hash_backfill, "SessionLocal", self.Session)
        self.session_patch.start()
        card_hash_backfill._running = False
        card_hash_backfill._last_result = None

    def tearDown(self):
        self.session_patch.stop()
        self.db.close()
        card_hash_backfill._running = False
        card_hash_backfill._last_result = None
        if card_hash_backfill._lock.locked():
            card_hash_backfill._lock.release()

    def _add_card(self, card_id):
        self.db.add(
            Card(
                id=card_id,
                tcg_card_id=card_id,
                name="Test",
                set_id="s1",
                number="1",
                lang="en",
                images_large=f"https://example.test/{card_id}.png",
            )
        )

    def test_hashes_a_new_card_and_records_last_result(self):
        self._add_card("a")
        self.db.commit()
        photo = _synthetic_card_photo_bytes()

        with patch("httpx.Client", return_value=_fake_httpx_client(photo)):
            result = card_hash_backfill.run_backfill(force=False)

        self.assertEqual(result, {"seen": 1, "hashed": 1, "failed": 0, "force": False})
        self.assertEqual(card_hash_backfill.last_result(), result)
        self.assertFalse(card_hash_backfill.is_running())
        stored = self.db.get(CardHash, "a")
        self.assertIsNotNone(stored)

    def test_incremental_run_skips_already_hashed_cards(self):
        self._add_card("a")
        self._add_card("b")
        self.db.add(CardHash(card_id="a", phash="0", dhash="0", whash="0"))
        self.db.commit()
        photo = _synthetic_card_photo_bytes()

        with patch("httpx.Client", return_value=_fake_httpx_client(photo)):
            result = card_hash_backfill.run_backfill(force=False)

        self.assertEqual(result["seen"], 1)  # only "b" was missing a hash

    def test_force_rehashes_cards_that_already_have_one(self):
        self._add_card("a")
        self.db.add(CardHash(card_id="a", phash="stale", dhash="stale", whash="stale"))
        self.db.commit()
        photo = _synthetic_card_photo_bytes()

        with patch("httpx.Client", return_value=_fake_httpx_client(photo)):
            result = card_hash_backfill.run_backfill(force=True)

        self.assertEqual(result["seen"], 1)
        self.assertNotEqual(self.db.get(CardHash, "a").phash, "stale")

    def test_a_failed_image_download_is_isolated_and_reported(self):
        self._add_card("a")
        self.db.commit()

        with patch("httpx.Client", return_value=_fake_httpx_client(b"", status_code=500)):
            result = card_hash_backfill.run_backfill(force=False)

        self.assertEqual(result, {"seen": 1, "hashed": 0, "failed": 1, "force": False})

    def test_concurrent_run_is_skipped_not_queued(self):
        self._add_card("a")
        self.db.commit()
        card_hash_backfill._lock.acquire()
        try:
            result = card_hash_backfill.run_backfill(force=False)
        finally:
            card_hash_backfill._lock.release()

        self.assertIsNone(result)
        self.assertIsNone(card_hash_backfill.last_result())


@unittest.skipUnless(DEPS_AVAILABLE, "opencv/imagehash/SQLAlchemy are not installed")
class CardHashesApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.admin = User(username="admin", hashed_password="x", role="admin", is_active=True)
        self.trainer = User(username="trainer", hashed_password="x", role="trainer", is_active=True)
        self.db.add_all([self.admin, self.trainer])
        self.db.commit()

        app = FastAPI()
        app.include_router(router, prefix="/api/card-hashes")

        def override_db():
            yield self.db

        app.dependency_overrides[get_db] = override_db
        self.app = app
        self.current_user = self.admin
        app.dependency_overrides[get_current_user] = lambda: self.current_user
        self.client = TestClient(app)

        card_hash_backfill._running = False
        card_hash_backfill._last_result = None

    def tearDown(self):
        self.client.close()
        self.db.close()
        card_hash_backfill._running = False
        card_hash_backfill._last_result = None

    def test_status_is_visible_to_any_authenticated_user(self):
        self.current_user = self.trainer
        with patch("api.card_hashes.hash_coverage_counts", return_value={
            "total_hashable": 0, "hashed": 0, "missing": 0,
        }):
            response = self.client.get("/api/card-hashes/status")
        self.assertEqual(response.status_code, 200)

    def test_status_reports_coverage_and_running_state(self):
        with patch("api.card_hashes.hash_coverage_counts", return_value={
            "total_hashable": 10, "hashed": 4, "missing": 6,
        }):
            response = self.client.get("/api/card-hashes/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total_hashable"], 10)
        self.assertFalse(body["is_running"])

    def test_backfill_trigger_is_admin_only(self):
        self.current_user = self.trainer
        response = self.client.post("/api/card-hashes/backfill", json={"force": False})
        self.assertEqual(response.status_code, 403)

    def test_backfill_trigger_starts_a_background_run(self):
        with patch("api.card_hashes.run_backfill") as run_mock:
            response = self.client.post("/api/card-hashes/backfill", json={"force": False})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "started")

    def test_backfill_trigger_reports_already_running_instead_of_double_starting(self):
        with patch("api.card_hashes.is_running", return_value=True):
            response = self.client.post("/api/card-hashes/backfill", json={"force": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "running")

    def test_reschedule_persists_setting_and_calls_scheduler(self):
        with patch("services.scheduler.reschedule_card_hash_backfill") as reschedule_mock:
            response = self.client.post(
                "/api/card-hashes/reschedule", json={"interval_minutes": 30}
            )
        self.assertEqual(response.status_code, 200)
        reschedule_mock.assert_called_once_with(30)
        from models import Setting
        row = self.db.query(Setting).filter(
            Setting.key == "card_hash_backfill_interval_minutes"
        ).first()
        self.assertEqual(row.value, "30")


if __name__ == "__main__":
    unittest.main()
