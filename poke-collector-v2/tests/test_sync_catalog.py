"""Tests for the catalog sync job.

Pure-logic tests (variant inference, cache path) run everywhere. The
end-to-end test hits tcgdex.dev for real (no mocks, same rationale as
tests/test_tcgdex_client.py) and skips gracefully when unreachable.
"""
from pathlib import Path

import cv2
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db.models import Base, Card, CardHash
from app.integrations.tcgdex_client import TcgdexApiError, TcgdexClient
from app.jobs.sync_catalog import _compute_hashes, _image_cache_path, _infer_variant, sync_set
from app.pipeline import hash_matcher, preprocess


@pytest.mark.parametrize(
    "rarity,expected",
    [
        (None, "normal"),
        ("Common", "normal"),
        ("Rare Holo", "holo"),
        ("Rare Holo VMAX", "holo"),
        ("Rare Reverse Holo", "reverse_holo"),
    ],
)
def test_infer_variant(rarity, expected):
    assert _infer_variant(rarity) == expected


def test_image_cache_path_uses_url_extension():
    path = _image_cache_path(
        Path("/data/catalog"), "base1-4", "https://assets.tcgdex.net/en/base/base1/4/high.webp"
    )
    assert path == Path("/data/catalog/images/tcgdex/base1-4.webp")


def test_image_cache_path_defaults_to_webp_without_extension():
    path = _image_cache_path(Path("/data/catalog"), "base1-4", "https://assets.tcgdex.net/en/base/base1/4")
    assert path.suffix == ".webp"


def test_compute_hashes_matches_scan_time_pipeline(tmp_path):
    """Regression: sync-time hashing must go through the exact same
    preprocess -> hash_matcher pipeline resolve_scan() uses at scan time.
    Hashing the raw cached file directly (no resize, no CLAHE) made
    reference hashes drift from what scanning that same image would
    produce — most cards still matched by luck, some (e.g. base1-4) didn't.
    """
    canvas = np.full((800, 900, 3), 230, dtype=np.uint8)
    ok, buf = cv2.imencode(".png", canvas)
    assert ok
    image_path = tmp_path / "ref.png"
    image_path.write_bytes(buf.tobytes())

    output_size = (200, 280)
    actual = _compute_hashes(image_path, output_size)
    expected = hash_matcher.compute_hashes(
        preprocess.preprocess_image(image_path.read_bytes(), output_size)
    )

    assert actual == expected


@pytest.mark.asyncio
async def test_sync_set_end_to_end(tmp_path):
    settings = Settings(database_path=tmp_path / "test.db", catalog_dir=tmp_path / "catalog")
    engine = create_engine(f"sqlite:///{settings.database_path}")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    try:
        async with TcgdexClient(settings) as api_client:
            import httpx as _httpx

            async with _httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http_client:
                try:
                    stats = await sync_set(
                        db,
                        api_client,
                        http_client,
                        settings.catalog_dir,
                        "base1",
                        output_size=settings.card_output_size,
                    )
                except TcgdexApiError as exc:
                    pytest.skip(f"tcgdex.dev unreachable in this environment: {exc}")

        assert stats["cards_hashed"] + stats["cards_skipped"] == stats["cards_seen"]
        assert stats["cards_seen"] >= 100

        charizard = db.get(Card, "base1-4")
        assert charizard is not None
        assert charizard.name == "Charizard"
        assert charizard.source_api == "tcgdex"

        charizard_hash = db.get(CardHash, "base1-4")
        assert charizard_hash is not None
        assert charizard_hash.phash and charizard_hash.dhash and charizard_hash.whash

        cached_files = list((settings.catalog_dir / "images" / "tcgdex").glob("*"))
        assert cached_files, "expected at least one cached reference image on disk"
    finally:
        db.close()
