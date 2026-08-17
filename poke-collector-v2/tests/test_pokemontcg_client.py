"""Live integration tests against api.pokemontcg.io.

These hit the real public API on purpose (no mocks) to catch upstream schema
drift early. They skip instead of failing when the network is unreachable
(e.g. restricted CI/sandbox), since this client is only meaningful with real
internet access — that's the same condition it needs in the homelab.
"""
import pytest

from app.integrations.pokemontcg_client import PokemonTcgApiError, PokemonTcgClient


@pytest.fixture
async def client():
    async with PokemonTcgClient() as c:
        yield c


async def _skip_if_unreachable(coro):
    try:
        return await coro
    except PokemonTcgApiError as exc:
        pytest.skip(f"pokemontcg.io unreachable in this environment: {exc}")


@pytest.mark.asyncio
async def test_list_sets_returns_known_set(client: PokemonTcgClient):
    sets = await _skip_if_unreachable(client.list_sets(page=1, page_size=250))
    assert sets, "expected at least one set"
    set_ids = {s["id"] for s in sets}
    assert "base1" in set_ids


@pytest.mark.asyncio
async def test_get_set_base1(client: PokemonTcgClient):
    result = await _skip_if_unreachable(client.get_set("base1"))
    assert result is not None
    assert result["id"] == "base1"
    assert result["name"] == "Base"


@pytest.mark.asyncio
async def test_get_card_charizard(client: PokemonTcgClient):
    card = await _skip_if_unreachable(client.get_card("base1-4"))
    assert card is not None
    assert card["name"] == "Charizard"
    assert card["set"]["id"] == "base1"


@pytest.mark.asyncio
async def test_get_card_missing_returns_none(client: PokemonTcgClient):
    card = await _skip_if_unreachable(client.get_card("does-not-exist-123"))
    assert card is None


@pytest.mark.asyncio
async def test_list_cards_for_set(client: PokemonTcgClient):
    cards = await _skip_if_unreachable(client.list_cards(set_id="base1", page_size=250))
    assert len(cards) >= 100
    assert all(c["set"]["id"] == "base1" for c in cards)
