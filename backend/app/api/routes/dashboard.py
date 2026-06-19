"""Dashboard, metrics, day-progress, coach routes."""
from __future__ import annotations
import json
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.date_utils import day_progress, get_active_date
from app.db.session import get_db
from app.models.health import CoachSummary, HealthSnapshot
from app.services import goals as goals_svc
from app.services.insights import RANGE_DAYS, correlations, dashboard_insights, metric_payload
from app.services.profile import actual_age_years, get_or_create_profile, profile_height_cm, profile_payload
from app.services.scoring import compute_fitness_age, compute_biological_age, fitness_age_drivers, biological_age_drivers
from app.services.special_metrics import special_metrics_payload

router = APIRouter(tags=["dashboard"])


class BodyCompositionInput(BaseModel):
    metric_date: date | None = Field(default=None, alias="date")
    weight_kg: float | None = Field(default=None, ge=30, le=250)
    body_fat_pct: float | None = Field(default=None, ge=3, le=60)
    muscle_mass_kg: float | None = Field(default=None, ge=10, le=120)


class ProfileInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    date_of_birth: date | None = None
    height_cm: float | None = Field(default=None, ge=100, le=230)
    weight_kg: float | None = Field(default=None, ge=30, le=250)
    body_fat_pct: float | None = Field(default=None, ge=3, le=60)
    muscle_mass_kg: float | None = Field(default=None, ge=10, le=120)


def _snap_or_none(db: Session, d: date) -> Optional[HealthSnapshot]:
    return db.execute(select(HealthSnapshot).where(HealthSnapshot.date == d)).scalar_one_or_none()


def _range_snaps(db: Session, end: date, days: int) -> list[HealthSnapshot]:
    start = end - timedelta(days=days - 1)
    rows = db.execute(
        select(HealthSnapshot)
        .where(HealthSnapshot.date >= start, HealthSnapshot.date <= end)
        .order_by(HealthSnapshot.date.asc())
    ).scalars().all()
    return list(rows)


def _latest_field_value(db: Session, end: date, field: str):
    row = db.execute(
        select(HealthSnapshot)
        .where(HealthSnapshot.date <= end, getattr(HealthSnapshot, field).isnot(None))
        .order_by(HealthSnapshot.date.desc())
        .limit(1)
    ).scalar_one_or_none()
    return getattr(row, field, None) if row else None


def _enrich_sparse_snapshot(db: Session, snap: HealthSnapshot | None, end: date) -> HealthSnapshot | None:
    if not snap:
        return snap
    for sparse_field in ("vo2max", "hr_recovery", "weight_kg", "body_fat_pct", "muscle_mass_kg", "bmi"):
        if getattr(snap, sparse_field, None) is None:
            setattr(snap, sparse_field, _latest_field_value(db, end, sparse_field))
    return snap


@router.get("/api/day-progress")
def day_progress_route():
    s = get_settings()
    return day_progress(wake_hour=s.wake_hour, sleep_hour=s.sleep_hour)


@router.get("/api/metrics/goal-completion-rate")
def goal_completion_rate(days: int = 7, db: Session = Depends(get_db)):
    return goals_svc.completion_rate_window(db, get_active_date(), days=days)


@router.get("/api/dashboard/today")
def dashboard_today(selected_date: date | None = Query(None, alias="date"), db: Session = Depends(get_db)):
    s = get_settings()
    d = selected_date or get_active_date()
    snap = _snap_or_none(db, d)
    goals = goals_svc.list_for_date(db, d)
    streak = goals_svc.get_streak(db)
    actual_age = actual_age_years(db)

    has_data = snap is not None and snap.source == "garmin"
    profile_info = profile_payload(db, d)

    def v(field):
        return getattr(snap, field, None) if snap else None

    def latest_v(field):
        direct = v(field)
        if direct is not None:
            return direct
        return _latest_field_value(db, d, field)

    snap = _enrich_sparse_snapshot(db, snap, d)

    # Fitness / Bio age
    fit_age, fit_status = compute_fitness_age(snap, actual_age) if snap else (None, None)
    bio_age, bio_status = compute_biological_age(snap, actual_age) if snap else (None, None)
    fit_drivers = fitness_age_drivers(snap, actual_age) if snap else []
    bio_drivers = biological_age_drivers(snap, actual_age) if snap else []

    return {
        "active_date": d.isoformat(),
        "has_garmin_data": has_data,
        "actual_age": actual_age,
        "profile": profile_info,
        "day_progress": day_progress(wake_hour=s.wake_hour, sleep_hour=s.sleep_hour),
        # Age scores
        "fitness_age": fit_age,
        "fitness_age_status": fit_status,
        "fitness_age_delta": round(fit_age - actual_age, 1) if fit_age else None,
        "fitness_age_drivers": fit_drivers or [],
        "biological_age": bio_age,
        "biological_age_status": bio_status,
        "biological_age_delta": round(bio_age - actual_age, 1) if bio_age else None,
        "biological_age_drivers": bio_drivers or [],
        # Rings
        "rings": [
            {"label": "Recovery", "value": int(v("recovery") or 0), "target": 100, "color": "--ring-recovery"},
            {"label": "Readiness", "value": int(v("readiness") or 0), "target": 100, "color": "--ring-readiness"},
            {"label": "Strain", "value": int(v("strain") or 0), "target": int(v("target_strain") or 100), "color": "--ring-strain"},
        ],
        # Metrics
        "metrics": {
            "recovery": v("recovery"),
            "readiness": v("readiness"),
            "strain": v("strain"),
            "target_strain": v("target_strain"),
            "sleep_score": v("sleep_score"),
            "sleep_hours": round(v("sleep_minutes") / 60, 1) if v("sleep_minutes") else None,
            "deep_sleep_hours": round(v("sleep_deep_minutes") / 60, 1) if v("sleep_deep_minutes") else None,
            "rem_sleep_hours": round(v("sleep_rem_minutes") / 60, 1) if v("sleep_rem_minutes") else None,
            "awake_time_hours": round(v("sleep_awake_minutes") / 60, 1) if v("sleep_awake_minutes") else None,
            "sleep_debt_hours": round(v("sleep_debt_minutes") / 60, 1) if v("sleep_debt_minutes") else None,
            "sleep_need_hours": round(v("sleep_need_minutes") / 60, 1) if v("sleep_need_minutes") else None,
            "hrv": v("hrv_ms"),
            "hrv_baseline": v("hrv_baseline_ms"),
            "rhr": v("rhr_bpm"),
            "rhr_baseline": v("rhr_baseline_bpm"),
            "max_hr": v("max_hr"),
            "hr_recovery": v("hr_recovery"),
            "body_battery": v("body_battery"),
            "stress": latest_v("stress"),
            "spo2": v("spo2_avg"),
            "respiration": v("respiration_avg"),
            "steps": v("steps"),
            "active_calories": v("active_calories"),
            "active_minutes": v("active_minutes"),
            "moderate_minutes": v("moderate_intensity_min"),
            "vigorous_minutes": v("vigorous_intensity_min"),
            "distance_km": v("distance_km"),
            "floors": v("floors_climbed"),
            "vo2max": latest_v("vo2max"),
            "cardio_load": v("cardio_load"),
            "load_balance": v("load_balance"),
            "weight_kg": profile_info["weight_kg"],
            "body_fat_pct": profile_info["body_fat_pct"],
            "muscle_mass_kg": profile_info["muscle_mass_kg"],
            "bmi": profile_info["bmi"],
        },
        "special_metrics": special_metrics_payload(db, d, "90d")["metrics"],
        # Goals
        "streak": streak.count,
        "goals_total": len(goals),
        "goals_completed": sum(1 for g in goals if g.done),
        "goals_queued": sum(1 for g in goals if g.queued and not g.done),
    }


@router.post("/api/body-composition")
def save_body_composition(payload: BodyCompositionInput, db: Session = Depends(get_db)):
    s = get_settings()
    if (
        payload.weight_kg is None
        and payload.body_fat_pct is None
        and payload.muscle_mass_kg is None
    ):
        raise HTTPException(status_code=400, detail="Enter at least one body composition value.")

    d = payload.metric_date or get_active_date()
    snap = _snap_or_none(db, d)
    if not snap:
        snap = HealthSnapshot(date=d, source="manual")
        db.add(snap)

    if payload.weight_kg is not None:
        snap.weight_kg = round(payload.weight_kg, 1)
    if payload.body_fat_pct is not None:
        snap.body_fat_pct = round(payload.body_fat_pct, 1)
    if payload.muscle_mass_kg is not None:
        snap.muscle_mass_kg = round(payload.muscle_mass_kg, 1)
    if snap.weight_kg:
        height_m = max(1.0, profile_height_cm(db) / 100)
        snap.bmi = round(snap.weight_kg / (height_m * height_m), 1)

    from app.services.garmin_sync import recompute_existing
    db.commit()
    recompute_existing(db)
    db.refresh(snap)
    return {
        "date": snap.date.isoformat(),
        "weight_kg": snap.weight_kg,
        "body_fat_pct": snap.body_fat_pct,
        "muscle_mass_kg": snap.muscle_mass_kg,
        "bmi": snap.bmi,
    }


@router.get("/api/profile")
def get_profile(db: Session = Depends(get_db)):
    return profile_payload(db, get_active_date())


@router.put("/api/profile")
def update_profile(payload: ProfileInput, db: Session = Depends(get_db)):
    profile = get_or_create_profile(db)
    if payload.name is not None:
        profile.name = payload.name.strip() or "Forge Athlete"
    if payload.date_of_birth is not None:
        profile.date_of_birth = payload.date_of_birth
    if payload.height_cm is not None:
        profile.height_cm = round(payload.height_cm, 1)

    body_fields = (payload.weight_kg, payload.body_fat_pct, payload.muscle_mass_kg)
    if any(value is not None for value in body_fields):
        d = get_active_date()
        snap = _snap_or_none(db, d)
        if not snap:
            snap = HealthSnapshot(date=d, source="manual")
            db.add(snap)
        if payload.weight_kg is not None:
            snap.weight_kg = round(payload.weight_kg, 1)
        if payload.body_fat_pct is not None:
            snap.body_fat_pct = round(payload.body_fat_pct, 1)
        if payload.muscle_mass_kg is not None:
            snap.muscle_mass_kg = round(payload.muscle_mass_kg, 1)
        if snap.weight_kg:
            height_m = max(1.0, (profile.height_cm or profile_height_cm(db)) / 100)
            snap.bmi = round(snap.weight_kg / (height_m * height_m), 1)

    db.commit()
    from app.services.garmin_sync import recompute_existing
    recompute_existing(db)
    return profile_payload(db, get_active_date())


@router.get("/api/metrics/{metric}")
def metric_series(
    metric: str,
    range: str = Query("30d", pattern="^(7d|30d|90d|6m|1y|all)$"),
    selected_date: date | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
):
    """Return a full drill-down payload for any metric field."""
    end = selected_date or date.today()
    try:
        payload = metric_payload(db, metric, range, end)
    except KeyError:
        raise HTTPException(404, f"Unknown metric: {metric}")
    return {**payload, "correlations": correlations(db, metric, range, end)}


@router.get("/api/insights")
def insights(
    range: str = Query("90d", pattern="^(7d|30d|90d|6m|1y|all)$"),
    selected_date: date | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
):
    if range not in RANGE_DAYS:
        raise HTTPException(400, f"Unsupported range: {range}")
    return dashboard_insights(db, range, selected_date or date.today())


@router.get("/api/special-metrics")
def special_metrics(
    range: str = Query("90d", pattern="^(7d|30d|90d|6m|1y|all)$"),
    selected_date: date | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
):
    if range not in RANGE_DAYS:
        raise HTTPException(400, f"Unsupported range: {range}")
    return special_metrics_payload(db, selected_date or date.today(), range)


@router.get("/api/fitness-age")
def fitness_age_detail(db: Session = Depends(get_db)):
    actual_age = actual_age_years(db)
    snap = _enrich_sparse_snapshot(db, _snap_or_none(db, get_active_date()), get_active_date())
    if not snap:
        return {"status": "no_data"}
    fit_age, fit_status = compute_fitness_age(snap, actual_age)
    drivers = fitness_age_drivers(snap, actual_age) or []
    trend = []
    for sn in _range_snaps(db, date.today(), 90):
        fa, _ = compute_fitness_age(sn, actual_age)
        if fa:
            trend.append({"date": sn.date.isoformat(), "value": fa})
    return {
        "actual_age": actual_age,
        "fitness_age": fit_age,
        "status": fit_status,
        "delta": round(fit_age - actual_age, 1) if fit_age else None,
        "drivers": drivers,
        "trend_90d": trend,
    }


@router.get("/api/biological-age")
def biological_age_detail(db: Session = Depends(get_db)):
    actual_age = actual_age_years(db)
    snap = _enrich_sparse_snapshot(db, _snap_or_none(db, get_active_date()), get_active_date())
    if not snap:
        return {"status": "no_data"}
    bio_age, bio_status = compute_biological_age(snap, actual_age)
    drivers = biological_age_drivers(snap, actual_age) or []
    trend = []
    for sn in _range_snaps(db, date.today(), 90):
        ba, _ = compute_biological_age(sn, actual_age)
        if ba:
            trend.append({"date": sn.date.isoformat(), "value": ba})
    return {
        "actual_age": actual_age,
        "biological_age": bio_age,
        "status": bio_status,
        "delta": round(bio_age - actual_age, 1) if bio_age else None,
        "drivers": drivers,
        "trend_90d": trend,
    }


@router.get("/api/coach/today")
def coach_today(db: Session = Depends(get_db)):
    from app.services.coach import recommendations
    return recommendations(db)


@router.post("/api/coach/generate")
def coach_generate(db: Session = Depends(get_db)):
    from app.services.coach import generate_ai_brief
    return generate_ai_brief(db)


@router.get("/api/coach/history")
def coach_history(limit: int = 14, db: Session = Depends(get_db)):
    rows = db.execute(
        select(CoachSummary).order_by(CoachSummary.date.desc()).limit(limit)
    ).scalars().all()
    return [
        {
            "id": r.id,
            "date": r.date.isoformat(),
            "headline": r.headline,
            "summary": r.summary,
            "observations": json.loads(r.observations_json),
            "actions": json.loads(r.actions_json),
            "risks": json.loads(r.risks_json),
            "confidence": r.confidence,
            "used_ai": r.used_ai,
        }
        for r in rows
    ]
