"""POST /api/v1/scan and /api/v1/scan/confirm (Fase 3-5)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.schemas import CardOut
from app.db.models import Card, ScanLog
from app.db.session import get_db
from app.pipeline.resolver import resolve_scan

router = APIRouter()


class CandidateOut(BaseModel):
    card_id: str
    combined_distance: int


class ScanResponse(BaseModel):
    scan_log_id: int | None
    status: str
    card_id: str | None
    confidence: float | None
    used_ocr_fallback: bool
    candidates: list[CandidateOut]


class ConfirmRequest(BaseModel):
    scan_log_id: int
    card_id: str


class ConfirmResponse(BaseModel):
    scan_log_id: int
    card: CardOut


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
        scan_log_id=result.scan_log_id,
        status=result.status,
        card_id=result.card_id,
        confidence=result.confidence,
        used_ocr_fallback=result.used_ocr_fallback,
        candidates=[
            CandidateOut(card_id=c.card_id, combined_distance=c.combined_distance)
            for c in result.candidates
        ],
    )


@router.post("/scan/confirm", response_model=ConfirmResponse)
def confirm_scan(payload: ConfirmRequest, db: Session = Depends(get_db)) -> ConfirmResponse:
    """Manually pick a candidate for a low-confidence /scan result.

    Updates the original scan_log row so later threshold tuning can see
    which manual picks the automated match missed or got wrong.
    """
    scan_log = db.get(ScanLog, payload.scan_log_id)
    if scan_log is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    card = db.get(Card, payload.card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found in catalog")

    scan_log.matched_card_id = card.id
    scan_log.confidence = 1.0  # manually confirmed
    db.commit()

    return ConfirmResponse(scan_log_id=scan_log.id, card=CardOut.model_validate(card))
