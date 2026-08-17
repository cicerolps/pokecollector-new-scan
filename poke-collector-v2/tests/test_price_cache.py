"""GET /api/v1/cards/{id}/price — TTL cache-or-refresh, no real network:
TcgdexClient is monkeypatched out entirely so these run everywhere.
"""
from datetime import datetime, timedelta, timezone

from app.api import collection as collection_module
from app.db.models import Card, CardPrice
from app.integrations.tcgdex_client import TcgdexApiError


def _fake_client_class(card_data, calls):
    class _FakeClient:
        def __init__(self, settings=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def get_card(self, card_id, *, lang=None):
            calls.append(card_id)
            return card_data

    return _FakeClient


def _failing_client_class():
    class _FailingClient:
        def __init__(self, settings=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def get_card(self, card_id, *, lang=None):
            raise TcgdexApiError("boom")

    return _FailingClient


def _seed_card(db_session, card_id="a") -> None:
    db_session.add(
        Card(id=card_id, source_api="tcgdex", name="A", set_id="s", set_name="S", number="1/1")
    )
    db_session.commit()


def test_get_card_price_404s_for_unknown_card(client):
    response = client.get("/api/v1/cards/does-not-exist/price")
    assert response.status_code == 404


def test_get_card_price_fetches_and_caches(client, db_session, monkeypatch):
    _seed_card(db_session)
    calls: list[str] = []
    monkeypatch.setattr(
        collection_module,
        "TcgdexClient",
        _fake_client_class({"pricing": {"cardmarket": {"avg": 5.5}}}, calls),
    )

    first = client.get("/api/v1/cards/a/price")
    assert first.status_code == 200
    body = first.json()
    assert body["market_price"] == 5.5
    assert body["currency"] == "EUR"
    assert len(calls) == 1

    # Within TTL: served from cache, no second fetch.
    second = client.get("/api/v1/cards/a/price")
    assert second.status_code == 200
    assert second.json()["market_price"] == 5.5
    assert len(calls) == 1


def test_get_card_price_refreshes_when_stale(client, db_session, monkeypatch):
    _seed_card(db_session)
    stale = datetime.now(timezone.utc) - timedelta(hours=48)
    db_session.add(
        CardPrice(card_id="a", market_price=1.0, currency="EUR", source="tcgdex", fetched_at=stale)
    )
    db_session.commit()

    calls: list[str] = []
    monkeypatch.setattr(
        collection_module,
        "TcgdexClient",
        _fake_client_class({"pricing": {"cardmarket": {"avg": 9.99}}}, calls),
    )

    response = client.get("/api/v1/cards/a/price")
    assert response.status_code == 200
    assert response.json()["market_price"] == 9.99
    assert len(calls) == 1


def test_get_card_price_falls_back_to_stale_cache_on_api_error(client, db_session, monkeypatch):
    _seed_card(db_session)
    stale = datetime.now(timezone.utc) - timedelta(hours=48)
    db_session.add(
        CardPrice(card_id="a", market_price=3.3, currency="EUR", source="tcgdex", fetched_at=stale)
    )
    db_session.commit()

    monkeypatch.setattr(collection_module, "TcgdexClient", _failing_client_class())

    response = client.get("/api/v1/cards/a/price")
    assert response.status_code == 200
    assert response.json()["market_price"] == 3.3


def test_get_card_price_returns_nulls_when_never_cached_and_unreachable(client, db_session, monkeypatch):
    _seed_card(db_session)
    monkeypatch.setattr(collection_module, "TcgdexClient", _failing_client_class())

    response = client.get("/api/v1/cards/a/price")
    assert response.status_code == 200
    body = response.json()
    assert body["market_price"] is None
    assert body["fetched_at"] is None
