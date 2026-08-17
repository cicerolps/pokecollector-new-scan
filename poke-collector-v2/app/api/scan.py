"""POST /api/v1/scan (Fase 3-4).

/api/v1/scan/confirm and GET /api/v1/cards/{id} are deferred to Fase 5,
alongside the collection endpoints they naturally pair with (confirming a
candidate and adding it to the collection are two steps of one flow, and
both need Card detail serialization that collection.py will also need).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.pipeline.resolver import resolve_scan

router = APIRouter()


class CandidateOut(BaseModel):
    card_id: str
    combined_distance: int


class ScanResponse(BaseModel):
    status: str
    card_id: str | None
    confidence: float | None
    used_ocr_fallback: bool
    candidates: list[CandidateOut]


@router.post("/scan", response_model=ScanResponse)
async def scan(image: UploadFile = File(...), db: Session = Depends(get_db)) -> ScanResponse:
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image upload")

    try:
        result = resolve_scan(db, image_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ScanResponse(
        status=result.status,
        card_id=result.card_id,
        confidence=result.confidence,
        used_ocr_fallback=result.used_ocr_fallback,
        candidates=[
            CandidateOut(card_id=c.card_id, combined_distance=c.combined_distance)
            for c in result.candidates
        ],
    )
