"""Response schemas shared across api/ routers, to avoid redefining CardOut
in both scan.py (scan/confirm) and collection.py (collection + card lookup).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    set_id: str
    set_name: str
    number: str
    rarity: str | None
    variant: str | None
    image_url: str | None
