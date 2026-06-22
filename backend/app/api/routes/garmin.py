"""User-scoped Garmin connection and sync routes."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.orm import Session

from app.api.routes.auth import current_user
from app.db.session import get_db
from app.models.account import UserAccount
from app.services import garmin_sync
from app.services.connections import (
    disconnect_garmin,
    get_connection,
    public_connection_status,
)
from app.services.rate_limit import enforce_rate_limit

router = APIRouter(tags=["garmin"])


class GarminConnectInput(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(min_length=1, max_length=200)


class GarminMfaInput(BaseModel):
    challenge_id: str = Field(min_length=20, max_length=200)
    code: SecretStr = Field(min_length=4, max_length=20)


def _connection_status(db: Session, user: UserAccount) -> dict:
    connection = get_connection(db, user.id)
    payload = public_connection_status(connection)
    age_hours = None
    is_stale = True
    if connection and connection.last_synced_at:
        synced_at = connection.last_synced_at
        if synced_at.tzinfo is None:
            synced_at = synced_at.replace(tzinfo=timezone.utc)
        age_hours = round((datetime.now(timezone.utc) - synced_at).total_seconds() / 3600, 1)
        is_stale = age_hours > 6
    latest_job = garmin_sync.latest_history_job(db, user.id)
    return {
        **payload,
        "email": payload["account"],  # legacy UI compatibility; never Garmin email.
        "message": (
            "Garmin connected for this account."
            if payload["configured"]
            else "Connect Garmin to import this account's health history."
        ),
        "last_sync_age_hours": age_hours,
        "is_stale": is_stale,
        "history_import": garmin_sync.job_payload(latest_job) if latest_job else None,
    }


@router.post("/api/garmin/connect")
def connect_garmin(
    payload: GarminConnectInput,
    request: Request,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_user),
):
    enforce_rate_limit(f"garmin-connect:{request.client.host if request.client else 'unknown'}:{user.id}", limit=6, window_seconds=900)
    try:
        return garmin_sync.connect_user_garmin(
            db,
            user.id,
            payload.email.strip(),
            payload.password.get_secret_value(),
        )
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/api/garmin/mfa/verify")
def verify_garmin_mfa(
    payload: GarminMfaInput,
    request: Request,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_user),
):
    enforce_rate_limit(f"garmin-mfa:{request.client.host if request.client else 'unknown'}:{user.id}", limit=8, window_seconds=600)
    try:
        return garmin_sync.complete_user_garmin_mfa(
            db,
            user.id,
            payload.challenge_id,
            payload.code.get_secret_value(),
        )
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/api/sync/garmin/status")
def garmin_status(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_user),
):
    return _connection_status(db, user)


@router.delete("/api/garmin/connection", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_garmin_route(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_user),
):
    disconnect_garmin(db, user.id)


@router.post("/api/sync/garmin")
def sync_garmin_today(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_user),
):
    connection = get_connection(db, user.id)
    if not connection or connection.status != "connected" or not connection.encrypted_token_blob:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Garmin is not connected for this Forge account. Connect it before syncing.",
        )
    history_job = garmin_sync.latest_history_job(db, user.id)
    if history_job and history_job.status in {"queued", "running"}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A Garmin history import is already running. Daily sync will resume when it finishes.",
        )
    result = garmin_sync.sync_today(db, user.id)
    if result["status"] == "error":
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=result["message"])
    return result


@router.post("/api/sync/garmin/history")
def sync_garmin_history(
    days: int = 365,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_user),
):
    connection = get_connection(db, user.id)
    if not connection or connection.status != "connected" or not connection.encrypted_token_blob:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Garmin is not connected for this Forge account. Connect it before importing history.",
        )
    try:
        return garmin_sync.sync_history(db, user.id, days=min(max(days, 1), 365))
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/api/sync/garmin/history/start")
def start_garmin_history_import(
    days: int = 365,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_user),
):
    connection = get_connection(db, user.id)
    if not connection or connection.status != "connected" or not connection.encrypted_token_blob:
        raise HTTPException(status.HTTP_409_CONFLICT, "Connect Garmin before importing history.")
    return garmin_sync.start_history_sync(db, user.id, days)


@router.get("/api/sync/garmin/history/jobs/{job_id}")
def garmin_history_import_status(
    job_id: int,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_user),
):
    job = garmin_sync.get_history_job(db, user.id, job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "History import job not found.")
    return garmin_sync.job_payload(job)


@router.post("/api/sync/garmin/recompute")
def recompute_existing_metrics(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_user),
):
    return garmin_sync.recompute_existing(db, user.id)
