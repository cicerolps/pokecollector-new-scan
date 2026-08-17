"""GET/POST /api/v1/collection and GET /api/v1/cards/{id} (Fase 5).

No migration from the original poke-collector container — confirmed with
the user there's no existing data worth preserving, so this is a fresh
CollectionItem table populated only from here on.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.schemas import CardOut
from app.db.models import Card, CollectionItem
from app.db.session import get_db

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


@router.get("/cards/{card_id}", response_model=CardOut)
def get_card(card_id: str, db: Session = Depends(get_db)) -> Card:
    card = db.get(Card, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


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
