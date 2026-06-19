"""Garmin sync routes — real implementation using garminconnect."""
from __future__ import annotations
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.health import HealthSnapshot
from app.services import garmin_sync

router = APIRouter(prefix="/api/sync", tags=["garmin"])


@router.post("/garmin")
def sync_garmin_today(db: Session = Depends(get_db)):
    result = garmin_sync.sync_today(db)
    if result["status"] == "error":
        raise HTTPException(status_code=502, detail=result["message"])
    return result


@router.post("/garmin/history")
def sync_garmin_history(days: int = 365, db: Session = Depends(get_db)):
    """Import historical data. Runs synchronously — may be slow for 365 days."""
    try:
        result = garmin_sync.sync_history(db, days=min(days, 365))
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/garmin/status")
def garmin_status(db: Session = Depends(get_db)):
    from app.core.config import get_settings
    s = get_settings()
    token_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "garmin_session", "oauth1_token.json"))
    has_tokens = os.path.exists(token_path)
    configured = bool(s.garmin_email and s.garmin_password) or has_tokens
    latest = db.execute(
        select(HealthSnapshot)
        .where(HealthSnapshot.source == "garmin")
        .order_by(HealthSnapshot.updated_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    last_synced_at = latest.updated_at.replace(tzinfo=timezone.utc).isoformat() if latest and latest.updated_at else None
    last_sync_age_hours = None
    is_stale = True
    if latest and latest.updated_at:
        last_sync_age_hours = round((datetime.utcnow() - latest.updated_at).total_seconds() / 3600, 1)
        is_stale = last_sync_age_hours > 6
    return {
        "configured": configured,
        "email": s.garmin_email[:4] + "****" if s.garmin_email else ("saved session" if has_tokens else None),
        "message": "Garmin credentials configured" if s.garmin_email else (
            "Saved Garmin session loaded" if has_tokens else "Set GARMIN_EMAIL and GARMIN_PASSWORD in your .env file"
        ),
        "last_synced_at": last_synced_at,
        "last_sync_age_hours": last_sync_age_hours,
        "is_stale": is_stale,
    }


@router.post("/garmin/recompute")
def recompute_existing_metrics(db: Session = Depends(get_db)):
    return garmin_sync.recompute_existing(db)
