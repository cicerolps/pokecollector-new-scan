"""SQLAlchemy models — schema per PROJECT_SPEC.md section 5.

All tables live in the single SQLite file at Settings.database_path. `cards` /
`card_hashes` / `card_prices` are populated by the sync job (Fase 2), never
hand-edited. `collection_items` and `scan_log` are written by the API.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Card(Base):
    """Catalog entry, sourced from pokemontcg.io or tcgdex.dev."""

    __tablename__ = "cards"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "swsh1-1"
    source_api: Mapped[str] = mapped_column(String, nullable=False)  # "pokemontcg" | "tcgdex"
    name: Mapped[str] = mapped_column(String, nullable=False)
    set_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    set_name: Mapped[str] = mapped_column(String, nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)  # "025/198"
    rarity: Mapped[str | None] = mapped_column(String, nullable=True)
    variant: Mapped[str | None] = mapped_column(String, nullable=True)  # normal|holo|reverse_holo
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CardHash(Base):
    """Perceptual hashes pre-computed for a catalog card image."""

    __tablename__ = "card_hashes"

    card_id: Mapped[str] = mapped_column(
        String, ForeignKey("cards.id"), primary_key=True
    )
    phash: Mapped[str | None] = mapped_column(String, nullable=True)
    dhash: Mapped[str | None] = mapped_column(String, nullable=True)
    whash: Mapped[str | None] = mapped_column(String, nullable=True)


class CardPrice(Base):
    """Price cache with its own TTL, separate from the (permanent) hash cache."""

    __tablename__ = "card_prices"

    card_id: Mapped[str] = mapped_column(
        String, ForeignKey("cards.id"), primary_key=True
    )
    market_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CollectionItem(Base):
    """User's collection. Fresh table — no migration from the original
    poke-collector container (confirmed with the user: no data worth
    preserving there)."""

    __tablename__ = "collection_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[str] = mapped_column(String, ForeignKey("cards.id"), nullable=False)
    condition: Mapped[str | None] = mapped_column(String, nullable=True)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    acquired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScanLog(Base):
    """Audit trail for scan attempts — used to tune matching thresholds."""

    __tablename__ = "scan_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    image_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    matched_card_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("cards.id"), nullable=True
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    used_ocr_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    candidates_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
