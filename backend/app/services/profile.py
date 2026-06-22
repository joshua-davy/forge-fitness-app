"""Per-account profile helpers.

No fallback DOB, email, height, or shared body data is used here. Missing
profile fields remain missing until the signed-in user provides them.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import UserAccount
from app.models.health import HealthSnapshot, UserProfile


def get_user_profile(db: Session, user_id: int) -> UserProfile | None:
    return db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    ).scalar_one_or_none()


def get_or_create_profile(db: Session, user: UserAccount) -> UserProfile:
    profile = get_user_profile(db, user.id)
    if profile:
        return profile
    profile = UserProfile(user_id=user.id, name=user.display_name or "Forge Athlete")
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def actual_age_years(db: Session, user_id: int) -> float | None:
    profile = get_user_profile(db, user_id)
    if not profile or not profile.date_of_birth:
        return None
    return round((date.today() - profile.date_of_birth).days / 365.25, 1)


def profile_height_cm(db: Session, user_id: int) -> float | None:
    profile = get_user_profile(db, user_id)
    return float(profile.height_cm) if profile and profile.height_cm else None


def latest_body_snapshot(db: Session, user_id: int, end: date | None = None) -> HealthSnapshot | None:
    query = select(HealthSnapshot).where(HealthSnapshot.user_id == user_id)
    if end is not None:
        query = query.where(HealthSnapshot.date <= end)
    return db.execute(
        query.where(
            (HealthSnapshot.weight_kg.isnot(None))
            | (HealthSnapshot.body_fat_pct.isnot(None))
            | (HealthSnapshot.muscle_mass_kg.isnot(None))
            | (HealthSnapshot.bmi.isnot(None))
        )
        .order_by(HealthSnapshot.date.desc())
        .limit(1)
    ).scalar_one_or_none()


def _latest_field(db: Session, user_id: int, field: str, end: date | None = None) -> float | None:
    column = getattr(HealthSnapshot, field)
    query = select(HealthSnapshot).where(
        HealthSnapshot.user_id == user_id,
        column.isnot(None),
    )
    if end is not None:
        query = query.where(HealthSnapshot.date <= end)
    row = db.execute(query.order_by(HealthSnapshot.date.desc()).limit(1)).scalar_one_or_none()
    return getattr(row, field, None) if row else None


def profile_payload(db: Session, user: UserAccount, end: date | None = None) -> dict:
    profile = get_or_create_profile(db, user)
    height = float(profile.height_cm) if profile.height_cm else None
    weight = _latest_field(db, user.id, "weight_kg", end)
    body_fat = _latest_field(db, user.id, "body_fat_pct", end)
    muscle = _latest_field(db, user.id, "muscle_mass_kg", end)
    bmi = _latest_field(db, user.id, "bmi", end)
    if bmi is None and weight is not None and height:
        bmi = round(weight / ((height / 100) ** 2), 1)
    return {
        "name": profile.name,
        "email": user.email,
        "date_of_birth": profile.date_of_birth.isoformat() if profile.date_of_birth else None,
        "sex": profile.sex,
        "height_cm": height,
        "actual_age": actual_age_years(db, user.id),
        "weight_kg": weight,
        "body_fat_pct": body_fat,
        "muscle_mass_kg": muscle,
        "bmi": bmi,
    }
