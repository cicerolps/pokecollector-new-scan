"""Integration tests for the full preprocess -> hash_matcher -> (ocr) chain,
using a synthetic photo whose exact hash we control by preprocessing it
ourselves first and storing that as the "reference" hash — no real card
photos or EasyOCR model needed.
"""
import cv2
import numpy as np
import pytest

from app.config import Settings
from app.db.models import Card, CardHash
from app.pipeline import hash_matcher, preprocess, resolver


def _synthetic_card_photo(fill_color=(40, 120, 200)) -> bytes:
    corners = [(220, 90), (710, 130), (680, 690), (190, 660)]
    canvas = np.full((800, 900, 3), 230, dtype=np.uint8)
    cv2.fillConvexPoly(canvas, np.array(corners, dtype=np.int32), fill_color)
    ok, buf = cv2.imencode(".png", canvas)
    assert ok
    return buf.tobytes()


@pytest.fixture
def settings():
    return Settings(
        hash_confidence_gap=10,
        hash_no_match_distance=60,
        card_output_width=200,
        card_output_height=280,
    )


def _seed_known_card(db_session, settings, photo: bytes, card_id: str) -> None:
    normalized = preprocess.preprocess_image(photo, settings.card_output_size)
    hashes = hash_matcher.compute_hashes(normalized)
    db_session.add(
        Card(id=card_id, source_api="tcgdex", name=card_id, set_id="s", set_name="S", number="1/1")
    )
    db_session.add(CardHash(card_id=card_id, **hashes))
    db_session.commit()


def test_resolve_scan_no_match_with_empty_catalog(db_session, settings):
    result = resolver.resolve_scan(db_session, _synthetic_card_photo(), settings=settings)
    assert result.status == "no_match"
    assert result.card_id is None


def test_resolve_scan_confident_match(db_session, settings):
    photo = _synthetic_card_photo()
    _seed_known_card(db_session, settings, photo, "known")

    result = resolver.resolve_scan(db_session, photo, settings=settings)

    assert result.status == "matched"
    assert result.card_id == "known"
    assert result.used_ocr_fallback is False
    assert result.confidence is not None and result.confidence > 0.9


def test_resolve_scan_ambiguous_resolved_by_ocr(db_session, settings, monkeypatch):
    photo = _synthetic_card_photo()
    normalized = preprocess.preprocess_image(photo, settings.card_output_size)
    hashes = hash_matcher.compute_hashes(normalized)

    db_session.add_all(
        [
            Card(id="a", source_api="tcgdex", name="A", set_id="s", set_name="S", number="1/1"),
            Card(id="b", source_api="tcgdex", name="B", set_id="s", set_name="S", number="2/1"),
        ]
    )
    # Two cards sharing the exact same hash -> gap 0 -> ambiguous no matter
    # how hash_confidence_gap is set.
    db_session.add(CardHash(card_id="a", **hashes))
    db_session.add(CardHash(card_id="b", **hashes))
    db_session.commit()

    winning_candidate = hash_matcher.Candidate("a", 0, 0, 0)
    monkeypatch.setattr(resolver.ocr_disambiguator, "disambiguate", lambda *a, **k: winning_candidate)

    result = resolver.resolve_scan(db_session, photo, settings=settings)

    assert result.status == "matched"
    assert result.card_id == "a"
    assert result.used_ocr_fallback is True


def test_resolve_scan_stays_ambiguous_when_ocr_inconclusive(db_session, settings, monkeypatch):
    photo = _synthetic_card_photo()
    normalized = preprocess.preprocess_image(photo, settings.card_output_size)
    hashes = hash_matcher.compute_hashes(normalized)

    db_session.add_all(
        [
            Card(id="a", source_api="tcgdex", name="A", set_id="s", set_name="S", number="1/1"),
            Card(id="b", source_api="tcgdex", name="B", set_id="s", set_name="S", number="2/1"),
        ]
    )
    db_session.add(CardHash(card_id="a", **hashes))
    db_session.add(CardHash(card_id="b", **hashes))
    db_session.commit()

    monkeypatch.setattr(resolver.ocr_disambiguator, "disambiguate", lambda *a, **k: None)

    result = resolver.resolve_scan(db_session, photo, settings=settings)

    assert result.status == "ambiguous"
    assert result.card_id is None
    assert len(result.candidates) == 2


def test_resolve_scan_logs_every_attempt(db_session, settings):
    from app.db.models import ScanLog

    photo = _synthetic_card_photo()
    resolver.resolve_scan(db_session, photo, settings=settings)
    assert db_session.query(ScanLog).count() == 1
