"""Local single-user profile helpers.

This is intentionally small and local-first. It gives Forge a persistent
profile base now, and can later be replaced by a real users table without
changing the dashboard contract much.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.health import HealthSnapshot, UserProfile


def default_date_of_birth() -> date:
    settings = get_settings()
    try:
        return date.fromisoformat(settings.user_date_of_birth)
    except ValueError:
        return date(settings.user_birth_year, 1, 1)


def get_user_profile(db: Session) -> UserProfile | None:
    return db.execute(select(UserProfile).where(UserProfile.id == 1)).scalar_one_or_none()


def get_or_create_profile(db: Session) -> UserProfile:
    profile = get_user_profile(db)
    if profile:
        return profile
    settings = get_settings()
    profile = UserProfile(
        id=1,
        name="Forge Athlete",
        date_of_birth=default_date_of_birth(),
        height_cm=settings.user_height_cm,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def actual_age_years(db: Session) -> float:
    profile = get_user_profile(db)
    dob = profile.date_of_birth if profile and profile.date_of_birth else default_date_of_birth()
    return round((date.today() - dob).days / 365.25, 1)


def profile_height_cm(db: Session) -> float:
    profile = get_user_profile(db)
    if profile and profile.height_cm:
        return float(profile.height_cm)
    return float(get_settings().user_height_cm)


def latest_body_snapshot(db: Session, end: date | None = None) -> HealthSnapshot | None:
    query = select(HealthSnapshot)
    if end is not None:
        query = query.where(HealthSnapshot.date <= end)
    return db.execute(
        query
        .where(
            (HealthSnapshot.weight_kg.isnot(None))
            | (HealthSnapshot.body_fat_pct.isnot(None))
            | (HealthSnapshot.muscle_mass_kg.isnot(None))
            | (HealthSnapshot.bmi.isnot(None))
        )
        .order_by(HealthSnapshot.date.desc())
        .limit(1)
    ).scalar_one_or_none()


def _latest_field(db: Session, field: str, end: date | None = None) -> float | None:
    column = getattr(HealthSnapshot, field)
    query = select(HealthSnapshot)
    if end is not None:
        query = query.where(HealthSnapshot.date <= end)
    row = db.execute(
        query
        .where(column.isnot(None))
        .order_by(HealthSnapshot.date.desc())
        .limit(1)
    ).scalar_one_or_none()
    return getattr(row, field, None) if row else None


def profile_payload(db: Session, end: date | None = None) -> dict:
    profile = get_or_create_profile(db)
    height = profile.height_cm or get_settings().user_height_cm
    weight = _latest_field(db, "weight_kg", end)
    body_fat = _latest_field(db, "body_fat_pct", end)
    muscle = _latest_field(db, "muscle_mass_kg", end)
    bmi = _latest_field(db, "bmi", end) or (round(weight / ((height / 100) ** 2), 1) if weight else None)
    return {
        "name": profile.name,
        "email": get_settings().garmin_email or None,
        "date_of_birth": (profile.date_of_birth or default_date_of_birth()).isoformat(),
        "height_cm": round(float(height), 1),
        "actual_age": actual_age_years(db),
        "weight_kg": weight,
        "body_fat_pct": body_fat,
        "muscle_mass_kg": muscle,
        "bmi": bmi,
    }
