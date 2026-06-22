"""Health snapshot — full daily metrics from Garmin + derived scores."""
from __future__ import annotations
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class HealthSnapshot(Base):
    __tablename__ = "health_snapshots"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_health_snapshot_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # user_id=0 is reserved for rows imported by pre-account Forge builds.
    # Application routes never read it for signed-in accounts.
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Recovery / readiness / strain
    recovery: Mapped[float | None] = mapped_column(Float, nullable=True)
    readiness: Mapped[float | None] = mapped_column(Float, nullable=True)
    strain: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_strain: Mapped[float | None] = mapped_column(Float, nullable=True)
    cardio_load: Mapped[float | None] = mapped_column(Float, nullable=True)
    load_balance: Mapped[float | None] = mapped_column(Float, nullable=True)  # acute/chronic ratio

    # Sleep
    sleep_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_deep_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_rem_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_light_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_awake_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_debt_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_need_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_start_local: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sleep_end_local: Mapped[str | None] = mapped_column(String(32), nullable=True)
    nap_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Heart metrics
    hrv_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    hrv_baseline_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    rhr_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    rhr_baseline_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    hr_recovery: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Autonomic / stress
    body_battery: Mapped[float | None] = mapped_column(Float, nullable=True)
    body_battery_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    body_battery_end: Mapped[float | None] = mapped_column(Float, nullable=True)
    stress: Mapped[float | None] = mapped_column(Float, nullable=True)
    stress_duration_rest_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stress_duration_low_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stress_duration_medium_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stress_duration_high_min: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Respiratory / oxygen
    spo2_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    spo2_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    respiration_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    respiration_sleep: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Activity
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    steps_goal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floors_climbed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    moderate_intensity_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vigorous_intensity_min: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Fitness
    vo2max: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Body composition
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    body_fat_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    muscle_mass_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    bone_mass_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    bmi: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Derived age scores
    fitness_age: Mapped[float | None] = mapped_column(Float, nullable=True)
    fitness_age_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    biological_age: Mapped[float | None] = mapped_column(Float, nullable=True)
    biological_age_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Source tracking
    source: Mapped[str] = mapped_column(String(32), default="stub", nullable=False)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CoachSummary(Base):
    __tablename__ = "coach_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    headline: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    observations_json: Mapped[str] = mapped_column(Text, default="[]")
    actions_json: Mapped[str] = mapped_column(Text, default="[]")
    risks_json: Mapped[str] = mapped_column(Text, default="[]")
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    used_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="Forge Athlete", nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[str] = mapped_column(String(20), default="unspecified", nullable=False)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UserPlanningProfile(Base):
    """Optional, user-owned inputs for fuel, schedule, and dashboard planning."""

    __tablename__ = "user_planning_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    body_goal: Mapped[str] = mapped_column(String(32), default="maintain", nullable=False)
    work_start_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    work_end_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commute_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferred_wake_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    desired_sleep_hours: Mapped[float] = mapped_column(Float, default=8.0, nullable=False)
    hidden_cards_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
