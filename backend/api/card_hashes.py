from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from api.auth import get_current_user
from sqlalchemy.orm import Session
from database import get_db
from models import Setting, User
from services.card_hash_backfill import hash_coverage_counts, is_running, last_result, run_backfill
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/status")
def get_card_hash_backfill_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Coverage and running state for the scanner's hash bank. Admin only,
    same as the sync status endpoint it sits next to."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return {
        "is_running": is_running(),
        "last_result": last_result(),
        **hash_coverage_counts(),
    }


@router.post("/backfill")
def trigger_card_hash_backfill(
    body: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger a card-hash backfill. Body: {"force": false}.

    force=false (default) only hashes cards that don't have one yet — the
    same incremental run the scheduler does on its own. force=true
    recomputes every hashable card's hashes from scratch, which can take a
    long time on a large catalogue; the frontend is expected to make the
    user confirm that twice before calling this with force=true.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    if is_running():
        return {"message": "Card-hash backfill already running", "status": "running"}

    force = bool(body.get("force", False))

    def run():
        try:
            run_backfill(force=force)
        except Exception:
            logger.exception("Background card-hash backfill failed")

    background_tasks.add_task(run)
    return {"message": "Card-hash backfill started", "status": "started", "force": force}


@router.post("/reschedule")
def reschedule_card_hash_backfill_endpoint(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reschedule the automatic incremental backfill. Body: {"interval_minutes": 15}"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.scheduler import reschedule_card_hash_backfill as _reschedule

    interval_minutes = int(body.get("interval_minutes", 15))
    row = db.query(Setting).filter(Setting.key == "card_hash_backfill_interval_minutes").first()
    if row:
        row.value = str(interval_minutes)
    else:
        db.add(Setting(key="card_hash_backfill_interval_minutes", value=str(interval_minutes)))
    db.commit()
    try:
        _reschedule(interval_minutes)
    except Exception:
        pass  # Scheduler may not be running in all contexts
    return {"message": f"Card-hash backfill rescheduled to every {interval_minutes} minutes"}
