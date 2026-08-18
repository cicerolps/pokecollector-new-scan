"""Tests for the local hash+OCR scanner that replaced Gemini.

Uses the same in-memory-SQLite pattern as test_scan_queue.py. Synthetic
images (filled quadrilaterals) exercise contour detection, warping, and
end-to-end hash matching without needing real card photos or a live
EasyOCR model.
"""
import asyncio
import unittest
from unittest.mock import patch

try:
    import cv2
    import numpy as np
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from database import Base
    from models import Card, CardHash, Set
    from services import card_scan_hash as hash_matcher
    from services import card_scan_ocr as ocr
    from services import card_scan_preprocess as preprocess
    from services.card_scan_hash import Candidate
    from services.card_scan_resolver import resolve_local_scan

    DEPS_AVAILABLE = True
except ModuleNotFoundError:
    DEPS_AVAILABLE = False


def _synthetic_card_photo(fill_color=(40, 120, 200)) -> bytes:
    corners = [(220, 90), (710, 130), (680, 690), (190, 660)]
    canvas = np.full((800, 900, 3), 230, dtype=np.uint8)
    cv2.fillConvexPoly(canvas, np.array(corners, dtype=np.int32), fill_color)
    ok, buf = cv2.imencode(".png", canvas)
    assert ok
    return buf.tobytes()


@unittest.skipUnless(DEPS_AVAILABLE, "opencv/imagehash/SQLAlchemy are not installed")
class PreprocessTests(unittest.TestCase):
    def test_find_card_corners_detects_a_rectangle(self):
        canvas = np.full((1000, 800, 3), 230, dtype=np.uint8)
        cv2.fillConvexPoly(
            canvas, np.array([(200, 100), (700, 100), (700, 700), (200, 700)], dtype=np.int32), (40, 120, 200)
        )
        found = preprocess.find_card_corners(canvas)
        self.assertIsNotNone(found)
        self.assertEqual(found.shape, (4, 2))

    def test_find_card_corners_rejects_non_card_shaped_internal_contour(self):
        """Regression: found live on the poke-collector-v2 sister project — a
        high-contrast region inside a card's own artwork (no photographed
        background at all) can form a clean 4-point contour that passes the
        area threshold but isn't card-shaped, and gets mistaken for the card.
        """
        canvas = np.full((1000, 800, 3), 230, dtype=np.uint8)
        banner = np.array([(50, 400), (750, 400), (750, 600), (50, 600)], dtype=np.int32)
        cv2.fillConvexPoly(canvas, banner, (10, 10, 10))
        self.assertIsNone(preprocess.find_card_corners(canvas))

    def test_preprocess_image_falls_back_when_no_contour_found(self):
        flat = np.full((400, 300, 3), 100, dtype=np.uint8)
        ok, buf = cv2.imencode(".png", flat)
        normalized = preprocess.preprocess_image(buf.tobytes(), output_size=(150, 200))
        self.assertEqual(normalized.shape[:2], (200, 150))

    def test_preprocess_image_rejects_undecodable_bytes(self):
        with self.assertRaises(ValueError):
            preprocess.preprocess_image(b"not an image", output_size=(100, 140))


@unittest.skipUnless(DEPS_AVAILABLE, "opencv/imagehash/SQLAlchemy are not installed")
class HashMatcherTests(unittest.TestCase):
    def test_hamming_distance_identical_hashes_is_zero(self):
        self.assertEqual(hash_matcher._hamming("ffff0000ffff0000", "ffff0000ffff0000"), 0)

    def test_hamming_distance_missing_hash_is_treated_as_max(self):
        self.assertEqual(hash_matcher._hamming(None, "ffff0000ffff0000"), 64)

    def test_evaluate_confidence_confident_when_gap_large(self):
        candidates = [Candidate("a", 2, 2, 2), Candidate("b", 20, 20, 20)]
        self.assertEqual(hash_matcher.evaluate_confidence(candidates), "confident")

    def test_evaluate_confidence_ambiguous_when_gap_small(self):
        candidates = [Candidate("a", 2, 2, 2), Candidate("b", 3, 3, 3)]
        self.assertEqual(hash_matcher.evaluate_confidence(candidates), "ambiguous")

    def test_evaluate_confidence_no_match_when_too_far(self):
        self.assertEqual(hash_matcher.evaluate_confidence([Candidate("a", 30, 30, 30)]), "no_match")

    def test_evaluate_confidence_empty_is_no_match(self):
        self.assertEqual(hash_matcher.evaluate_confidence([]), "no_match")


@unittest.skipUnless(DEPS_AVAILABLE, "opencv/imagehash/SQLAlchemy are not installed")
class OcrNumberMatchTests(unittest.TestCase):
    def test_matches_local_number_and_printed_total(self):
        self.assertTrue(ocr._numbers_match("25", "198", "025", 198))

    def test_accepts_local_number_alone_when_total_unknown_locally(self):
        self.assertTrue(ocr._numbers_match("25", "198", "25", None))

    def test_rejects_wrong_local_number(self):
        self.assertFalse(ocr._numbers_match("25", "198", "99", 198))

    def test_rejects_wrong_total_when_known(self):
        self.assertFalse(ocr._numbers_match("25", "198", "25", 150))


@unittest.skipUnless(DEPS_AVAILABLE, "opencv/imagehash/SQLAlchemy are not installed")
class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()

    def _add_card(self, card_id, *, name="Known", number="1", set_id="s1", lang="en"):
        self.db.add(
            Card(
                id=card_id,
                tcg_card_id=card_id,
                name=name,
                set_id=set_id,
                number=number,
                lang=lang,
                images_large=f"https://example.test/{card_id}.png",
            )
        )

    def test_resolve_local_scan_no_match_with_empty_catalog(self):
        photo = _synthetic_card_photo()
        result = resolve_local_scan(self.db, photo)
        self.assertEqual(result["matches"], [])
        self.assertFalse(result["_identity_confident"])

    def test_resolve_local_scan_confident_match(self):
        photo = _synthetic_card_photo()
        normalized = preprocess.preprocess_image(photo, (600, 825))
        hashes = hash_matcher.compute_hashes(normalized)

        self._add_card("known-1")
        self.db.add(CardHash(card_id="known-1", **hashes))
        self.db.commit()

        result = resolve_local_scan(self.db, photo)

        self.assertTrue(result["_identity_confident"])
        self.assertEqual(result["_identity_decision"], "hash")
        self.assertEqual(result["matches"][0]["id"], "known-1")
        self.assertEqual(result["matches"][0]["tcg_card_id"], "known-1")

    def test_resolve_local_scan_ambiguous_resolved_by_ocr(self):
        photo = _synthetic_card_photo()
        normalized = preprocess.preprocess_image(photo, (600, 825))
        hashes = hash_matcher.compute_hashes(normalized)

        self._add_card("a", number="1")
        self._add_card("b", number="2")
        self.db.add(CardHash(card_id="a", **hashes))
        self.db.add(CardHash(card_id="b", **hashes))  # identical hash -> ambiguous
        self.db.commit()

        with patch.object(
            ocr, "disambiguate", return_value=Candidate("a", 0, 0, 0)
        ):
            result = resolve_local_scan(self.db, photo)

        self.assertTrue(result["_identity_confident"])
        self.assertEqual(result["_identity_decision"], "hash_ocr")
        self.assertEqual(result["matches"][0]["id"], "a")

    def test_resolve_local_scan_stays_ambiguous_when_ocr_inconclusive(self):
        photo = _synthetic_card_photo()
        normalized = preprocess.preprocess_image(photo, (600, 825))
        hashes = hash_matcher.compute_hashes(normalized)

        self._add_card("a", number="1")
        self._add_card("b", number="2")
        self.db.add(CardHash(card_id="a", **hashes))
        self.db.add(CardHash(card_id="b", **hashes))
        self.db.commit()

        with patch.object(ocr, "disambiguate", return_value=None):
            result = resolve_local_scan(self.db, photo)

        self.assertFalse(result["_identity_confident"])
        self.assertIsNone(result["_identity_decision"])
        self.assertEqual(len(result["matches"]), 2)


@unittest.skipUnless(DEPS_AVAILABLE, "opencv/imagehash/SQLAlchemy are not installed")
class RecognizeSanitizedCardTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()

    def test_rejects_undecodable_image_with_400(self):
        from fastapi import HTTPException

        from api.recognize import recognize_sanitized_card

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                recognize_sanitized_card(self.db, 1, b"not an image", "image/jpeg")
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_no_match_returns_a_well_formed_result(self):
        from api.recognize import recognize_sanitized_card

        result = asyncio.run(
            recognize_sanitized_card(self.db, 1, _synthetic_card_photo(), "image/jpeg")
        )
        self.assertEqual(result["matches"], [])
        self.assertFalse(result["_identity_confident"])


if __name__ == "__main__":
    unittest.main()
