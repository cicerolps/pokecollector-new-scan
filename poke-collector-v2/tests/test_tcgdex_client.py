"""Live integration tests against api.tcgdex.net.

Same rationale as test_pokemontcg_client.py: real requests, no mocks, skip
(don't fail) when the network is unreachable.
"""
import pytest

from app.integrations.tcgdex_client import TcgdexApiError, TcgdexClient


@pytest.fixture
async def client():
    async with TcgdexClient() as c:
        yield c


async def _skip_if_unreachable(coro):
    try:
        return await coro
    except TcgdexApiError as exc:
        pytest.skip(f"tcgdex.dev unreachable in this environment: {exc}")


@pytest.mark.asyncio
async def test_list_sets_returns_known_set(client: TcgdexClient):
    sets = await _skip_if_unreachable(client.list_sets(lang="en"))
    assert sets, "expected at least one set"
    set_ids = {s["id"] for s in sets}
    assert "base1" in set_ids


@pytest.mark.asyncio
async def test_get_set_base1(client: TcgdexClient):
    result = await _skip_if_unreachable(client.get_set("base1", lang="en"))
    assert result is not None
    assert result["id"] == "base1"
    assert result["cardCount"]["total"] > 0


@pytest.mark.asyncio
async def test_get_card_charizard(client: TcgdexClient):
    card = await _skip_if_unreachable(client.get_card("base1-4", lang="en"))
    assert card is not None
    assert card["name"] == "Charizard"


@pytest.mark.asyncio
async def test_get_card_missing_returns_none(client: TcgdexClient):
    card = await _skip_if_unreachable(client.get_card("does-not-exist-123", lang="en"))
    assert card is None


@pytest.mark.asyncio
async def test_list_set_cards(client: TcgdexClient):
    cards = await _skip_if_unreachable(client.list_set_cards("base1", lang="en"))
    assert len(cards) >= 100
