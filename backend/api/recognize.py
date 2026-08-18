import logging

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from api.auth import get_current_user
from database import get_db
from models import User
from services.scan_storage import MAX_FILE_BYTES, ScanUploadError, read_limited_upload, sanitize_image_bytes
from services.scan_trace import ScanTrace, create_scan_trace

logger = logging.getLogger(__name__)

router = APIRouter()


async def recognize_sanitized_card(
    db: Session,
    user_id: int,
    image_bytes: bytes,
    content_type: str,
    *,
    trace: ScanTrace | None = None,
) -> dict:
    """Recognize one already-sanitized image using the local hash+OCR
    scanner (services/card_scan_resolver.py) — no external API call, no
    per-user API key needed. content_type is accepted for signature
    compatibility with existing callers but unused: preprocess_image()
    decodes the bytes directly regardless of the original MIME type.
    """
    from services.card_scan_resolver import resolve_local_scan

    try:
        result = resolve_local_scan(db, image_bytes)
    except ValueError as exc:
        if trace:
            trace.record_error(f"Could not process image: {exc}")
        raise HTTPException(status_code=400, detail=f"Could not process image: {exc}")
    except Exception as exc:
        if trace:
            trace.record_error(f"Recognition failed: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail=f"Recognition failed: {exc}")

    if trace:
        selected = None
        if result.get("_identity_confident") and result.get("matches"):
            selected = result["matches"][0].get("tcg_card_id")
        trace.record_decision(result.get("_identity_decision") or "no_match", selected)

    return result


@router.post("/recognize")
async def recognize_card(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        raw_image = await read_limited_upload(file, remaining_job_bytes=MAX_FILE_BYTES)
        sanitized = sanitize_image_bytes(raw_image)
    except ScanUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    trace = create_scan_trace(
        db,
        current_user.id,
        mode="single",
        filename="sanitized-upload.jpg",
        model="local-hash-ocr",
    )
    trace.set_image(sanitized.data)
    try:
        return await recognize_sanitized_card(
            db,
            current_user.id,
            sanitized.data,
            sanitized.content_type,
            trace=trace,
        )
    finally:
        trace.save()
