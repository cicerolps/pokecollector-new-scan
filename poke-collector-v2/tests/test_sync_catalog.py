"""Tests for the catalog sync job.

Pure-logic tests (variant inference, cache path) run everywhere. The
end-to-end test hits tcgdex.dev for real (no mocks, same rationale as
tests/test_tcgdex_client.py) and skips gracefully when unreachable.
"""
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db.models import Base, Card, CardHash
from app.integrations.tcgdex_client import TcgdexApiError, TcgdexClient
from app.jobs.sync_catalog import _image_cache_path, _infer_variant, sync_set


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
                        db, api_client, http_client, settings.catalog_dir, "base1"
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
