"""Tests for the local hash+OCR scanner that replaced Gemini.

Uses the same in-memory-SQLite pattern as test_scan_queue.py. Synthetic
images (filled quadrilaterals) exercise contour detection, warping, and
end-to-end hash matching without needing real card photos or a live
EasyOCR model — field extraction itself is mocked at the resolver's `ocr`
entry point in tests that reach that stage, since a real EasyOCR read
needs baked model weights this environment doesn't have.
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
    from services import card_scan_resolver as resolver
    from services.card_scan_hash import Candidate

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


def _empty_fields(**overrides) -> dict:
    fields = {"name": None, "number": None, "total": None, "artist": None, "set_code": None}
    fields.update(overrides)
    return fields


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
class OcrFieldExtractionTests(unittest.TestCase):
    def test_extract_number_and_total_from_text(self):
        self.assertEqual(ocr.extract_number_and_total("some noise 25/198 more noise"), ("25", "198"))

    def test_extract_number_and_total_missing_returns_none(self):
        self.assertEqual(ocr.extract_number_and_total("no number here"), (None, None))

    def test_extract_artist_from_illus_prefix(self):
        self.assertEqual(ocr.extract_artist("Illus. akagi"), "akagi")

    def test_extract_artist_missing_returns_none(self):
        self.assertIsNone(ocr.extract_artist("no credit line"))

    def test_extract_set_code_skips_the_illustrator_name(self):
        self.assertEqual(ocr.extract_set_code("Illus akagi PBL 108 084", exclude="akagi"), "PBL")

    def test_name_similarity_tolerates_case_and_punctuation(self):
        self.assertGreater(ocr.name_similarity("Gladion's Final Battle", "gladions final battle!"), 0.9)

    def test_name_similarity_missing_value_is_zero(self):
        self.assertEqual(ocr.name_similarity(None, "Weedle"), 0.0)

    def test_numbers_match_local_and_total(self):
        self.assertTrue(ocr.numbers_match("25", "198", "025", 198))

    def test_numbers_match_accepts_local_alone_when_total_unknown_locally(self):
        self.assertTrue(ocr.numbers_match("25", "198", "25", None))

    def test_numbers_match_rejects_wrong_local(self):
        self.assertFalse(ocr.numbers_match("25", "198", "99", 198))

    def test_numbers_match_rejects_wrong_total_when_known(self):
        self.assertFalse(ocr.numbers_match("25", "198", "25", 150))


@unittest.skipUnless(DEPS_AVAILABLE, "opencv/imagehash/SQLAlchemy are not installed")
class ScoreCandidateTests(unittest.TestCase):
    def _card(self, **overrides):
        defaults = dict(number="25", artist="Ken Sugimori", name="Weedle")
        defaults.update(overrides)
        return Card(id="c1", tcg_card_id="c1", set_id="s1", lang="en", **defaults)

    def _set(self, **overrides):
        defaults = dict(printed_total=198, abbreviation="PBL")
        defaults.update(overrides)
        return Set(id="s1_en", tcg_set_id="s1", lang="en", name="Test Set", **defaults)

    def test_no_fields_is_neutral_zero(self):
        self.assertEqual(resolver.score_candidate(self._card(), self._set(), _empty_fields()), 0)

    def test_matching_number_scores_and_matching_total_adds_bonus(self):
        score = resolver.score_candidate(self._card(), self._set(), _empty_fields(number="25", total="198"))
        self.assertEqual(score, resolver._NUMBER_SCORE + resolver._TOTAL_SCORE)

    def test_wrong_number_excludes_the_candidate(self):
        score = resolver.score_candidate(self._card(), self._set(), _empty_fields(number="99", total="198"))
        self.assertIsNone(score)

    def test_matching_name_scores(self):
        score = resolver.score_candidate(self._card(), self._set(), _empty_fields(name="Weedle"))
        self.assertEqual(score, resolver._NAME_SCORE)

    def test_dissimilar_name_does_not_exclude_just_scores_nothing(self):
        score = resolver.score_candidate(self._card(), self._set(), _empty_fields(name="Completely Different Card"))
        self.assertEqual(score, 0)

    def test_matching_artist_scores(self):
        score = resolver.score_candidate(self._card(), self._set(), _empty_fields(artist="Ken Sugimori"))
        self.assertEqual(score, resolver._ARTIST_SCORE)

    def test_matching_set_code_scores(self):
        score = resolver.score_candidate(self._card(), self._set(), _empty_fields(set_code="PBL"))
        self.assertEqual(score, resolver._SET_CODE_SCORE)

    def test_all_fields_matching_stack_additively(self):
        fields = _empty_fields(number="25", total="198", name="Weedle", artist="Ken Sugimori", set_code="PBL")
        score = resolver.score_candidate(self._card(), self._set(), fields)
        expected = (
            resolver._NUMBER_SCORE + resolver._TOTAL_SCORE + resolver._NAME_SCORE
            + resolver._ARTIST_SCORE + resolver._SET_CODE_SCORE
        )
        self.assertEqual(score, expected)

    def test_missing_set_row_does_not_crash_total_or_set_code_checks(self):
        score = resolver.score_candidate(self._card(), None, _empty_fields(number="25", total="198", set_code="PBL"))
        self.assertEqual(score, resolver._NUMBER_SCORE)


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

    def _add_card(self, card_id, *, name="Known", number="1", set_id="s1", lang="en", artist=None):
        self.db.add(
            Card(
                id=card_id,
                tcg_card_id=card_id,
                name=name,
                set_id=set_id,
                number=number,
                lang=lang,
                artist=artist,
                images_large=f"https://example.test/{card_id}.png",
            )
        )

    def _hash_for(self, photo):
        normalized = preprocess.preprocess_image(photo, (600, 825))
        return hash_matcher.compute_hashes(normalized)

    def test_resolve_local_scan_no_match_with_empty_catalog(self):
        photo = _synthetic_card_photo()
        result = resolver.resolve_local_scan(self.db, photo)
        self.assertEqual(result["matches"], [])
        self.assertFalse(result["_identity_confident"])
        self.assertIsNone(result["_identity_decision"])

    def test_confident_via_hash_gap_when_fields_are_uninformative(self):
        photo = _synthetic_card_photo()
        self._add_card("known-1")
        self.db.add(CardHash(card_id="known-1", **self._hash_for(photo)))
        self.db.commit()

        with patch.object(resolver.ocr, "extract_fields", return_value=_empty_fields()):
            result = resolver.resolve_local_scan(self.db, photo)

        self.assertTrue(result["_identity_confident"])
        self.assertEqual(result["_identity_decision"], "hash")
        self.assertEqual(result["matches"][0]["id"], "known-1")

    def test_ambiguous_hash_resolved_by_a_uniquely_matching_number(self):
        photo = _synthetic_card_photo()
        hashes = self._hash_for(photo)
        self._add_card("a", number="1")
        self._add_card("b", number="2")
        self.db.add(CardHash(card_id="a", **hashes))
        self.db.add(CardHash(card_id="b", **hashes))  # identical hash -> ambiguous by hash alone
        self.db.commit()

        with patch.object(resolver.ocr, "extract_fields", return_value=_empty_fields(number="1", total=None)):
            result = resolver.resolve_local_scan(self.db, photo)

        self.assertTrue(result["_identity_confident"])
        self.assertEqual(result["_identity_decision"], "hash_fields")
        self.assertEqual(result["matches"][0]["id"], "a")

    def test_number_contradiction_removes_a_candidate_from_the_results_entirely(self):
        photo = _synthetic_card_photo()
        hashes = self._hash_for(photo)
        self._add_card("a", number="1")
        self._add_card("b", number="2")
        self.db.add(CardHash(card_id="a", **hashes))
        self.db.add(CardHash(card_id="b", **hashes))
        self.db.commit()

        # OCR read "2" — contradicts "a" (number=1), so "a" should be dropped
        # entirely rather than merely ranked below "b".
        with patch.object(resolver.ocr, "extract_fields", return_value=_empty_fields(number="2", total=None)):
            result = resolver.resolve_local_scan(self.db, photo)

        self.assertEqual([m["id"] for m in result["matches"]], ["b"])
        self.assertTrue(result["_identity_confident"])

    def test_stays_ambiguous_when_fields_do_not_discriminate_and_hash_gap_is_small(self):
        photo = _synthetic_card_photo()
        hashes = self._hash_for(photo)
        self._add_card("a", number="1")
        self._add_card("b", number="2")
        self.db.add(CardHash(card_id="a", **hashes))
        self.db.add(CardHash(card_id="b", **hashes))
        self.db.commit()

        # OCR found nothing usable for either card to key off of.
        with patch.object(resolver.ocr, "extract_fields", return_value=_empty_fields()):
            result = resolver.resolve_local_scan(self.db, photo)

        self.assertFalse(result["_identity_confident"])
        self.assertIsNone(result["_identity_decision"])
        self.assertEqual(len(result["matches"]), 2)

    def test_all_candidates_excluded_falls_back_to_original_hash_order_for_review(self):
        photo = _synthetic_card_photo()
        hashes = self._hash_for(photo)
        self._add_card("a", number="1")
        self._add_card("b", number="2")
        self.db.add(CardHash(card_id="a", **hashes))
        self.db.add(CardHash(card_id="b", **hashes))
        self.db.commit()

        # OCR read a number that matches neither candidate.
        with patch.object(resolver.ocr, "extract_fields", return_value=_empty_fields(number="9", total=None)):
            result = resolver.resolve_local_scan(self.db, photo)

        self.assertEqual({m["id"] for m in result["matches"]}, {"a", "b"})
        self.assertFalse(result["_identity_confident"])


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
