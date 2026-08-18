"""GET/POST /api/v1/collection, GET /api/v1/cards/{id} (Fase 5), and
GET /api/v1/cards/{id}/price (Fase 6 — TTL price cache, PROJECT_SPEC.md 4.2).

No migration from the original poke-collector container — confirmed with
the user there's no existing data worth preserving, so this is a fresh
CollectionItem table populated only from here on.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.schemas import CardOut
from app.config import Settings, get_settings
from app.db.models import Card, CardPrice, CollectionItem
from app.db.session import get_db
from app.integrations.tcgdex_client import TcgdexApiError, TcgdexClient, extract_market_price

router = APIRouter()


class CollectionItemCreate(BaseModel):
    card_id: str
    quantity: int = 1
    condition: str | None = None
    language: str | None = None
    notes: str | None = None
    acquired_at: datetime | None = None


class CollectionItemOut(BaseModel):
    id: int
    card: CardOut
    quantity: int
    condition: str | None
    language: str | None
    acquired_at: datetime | None
    notes: str | None


def _to_out(item: CollectionItem, card: Card) -> CollectionItemOut:
    return CollectionItemOut(
        id=item.id,
        card=CardOut.model_validate(card),
        quantity=item.quantity,
        condition=item.condition,
        language=item.language,
        acquired_at=item.acquired_at,
        notes=item.notes,
    )


class CardPriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    card_id: str
    market_price: float | None
    currency: str | None
    source: str | None
    fetched_at: datetime | None


def _is_fresh(price: CardPrice, settings: Settings) -> bool:
    if price.fetched_at is None:
        return False
    fetched_at = price.fetched_at
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - fetched_at < timedelta(hours=settings.price_cache_ttl_hours)


async def _get_or_refresh_price(
    db: Session, card: Card, settings: Settings
) -> CardPrice | None:
    cached = db.get(CardPrice, card.id)
    if cached and _is_fresh(cached, settings):
        return cached

    try:
        async with TcgdexClient(settings) as client:
            card_data = await client.get_card(card.id, lang=settings.tcgdex_default_lang)
    except TcgdexApiError:
        # tcgdex.dev unreachable/erroring — serve whatever's cached (even
        # stale) rather than fail the request over a price refresh.
        return cached

    if card_data is None:
        return cached

    market_price, currency = extract_market_price(card_data)
    if market_price is None:
        return cached

    refreshed = db.merge(
        CardPrice(
            card_id=card.id,
            market_price=market_price,
            currency=currency,
            source="tcgdex",
            fetched_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return refreshed


@router.get("/cards/{card_id}", response_model=CardOut)
def get_card(card_id: str, db: Session = Depends(get_db)) -> Card:
    card = db.get(Card, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@router.get("/cards/{card_id}/price", response_model=CardPriceOut)
async def get_card_price(card_id: str, db: Session = Depends(get_db)) -> CardPriceOut:
    card = db.get(Card, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")

    price = await _get_or_refresh_price(db, card, get_settings())
    if price is None:
        return CardPriceOut(card_id=card_id, market_price=None, currency=None, source=None, fetched_at=None)
    return CardPriceOut.model_validate(price)


@router.get("/collection", response_model=list[CollectionItemOut])
def list_collection(db: Session = Depends(get_db)) -> list[CollectionItemOut]:
    items = db.query(CollectionItem).order_by(CollectionItem.id.desc()).all()
    results = []
    for item in items:
        card = db.get(Card, item.card_id)
        if card is None:
            # Catalog row gone (e.g. re-synced under a different id) — skip
            # rather than 500 the whole listing over one stale reference.
            continue
        results.append(_to_out(item, card))
    return results


@router.post("/collection", response_model=CollectionItemOut, status_code=201)
def add_to_collection(
    payload: CollectionItemCreate, db: Session = Depends(get_db)
) -> CollectionItemOut:
    card = db.get(Card, payload.card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found in catalog")

    item = CollectionItem(
        card_id=payload.card_id,
        quantity=payload.quantity,
        condition=payload.condition,
        language=payload.language,
        notes=payload.notes,
        acquired_at=payload.acquired_at,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return _to_out(item, card)
