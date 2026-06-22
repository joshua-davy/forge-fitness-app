"""Deterministic personal planning tools built on Forge's owned health data.

These are decision aids, not medical or dietary prescriptions. Every payload
includes coverage/confidence so sparse Garmin history does not look certain.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from math import pow
from statistics import mean, median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Workout
from app.models.health import HealthSnapshot, UserPlanningProfile, UserProfile


GOALS = {"maintain", "lose_weight", "gain_weight", "gain_muscle", "lose_fat"}
CARD_IDS = {
    "home_rings", "home_coach", "home_markers", "home_ages", "home_patterns",
    "fitness_forecasts", "fitness_nutrition", "sleep_schedule", "sleep_explorer",
}


def _minute_label(value: int | None) -> str | None:
    if value is None:
        return None
    hour, minute = divmod(value % (24 * 60), 60)
    return f"{hour:02d}:{minute:02d}"


def _time_to_minute(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.hour * 60 + parsed.minute
    except ValueError:
        return None


def _sleep_clock_minute(value: str | None) -> int | None:
    minute = _time_to_minute(value)
    if minute is None:
        return None
    # Treat after-midnight bedtimes as part of the same evening window.
    return minute + 24 * 60 if minute < 12 * 60 else minute


def _profile(db: Session, user_id: int) -> UserProfile | None:
    return db.execute(select(UserProfile).where(UserProfile.user_id == user_id)).scalar_one_or_none()


def get_or_create_planning(db: Session, user_id: int) -> UserPlanningProfile:
    item = db.execute(
        select(UserPlanningProfile).where(UserPlanningProfile.user_id == user_id)
    ).scalar_one_or_none()
    if item:
        return item
    item = UserPlanningProfile(user_id=user_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _hidden_cards(item: UserPlanningProfile) -> list[str]:
    try:
        values = json.loads(item.hidden_cards_json or "[]")
    except (TypeError, ValueError):
        return []
    return [value for value in values if value in CARD_IDS] if isinstance(values, list) else []


def planning_settings_payload(db: Session, user_id: int) -> dict:
    item = get_or_create_planning(db, user_id)
    return {
        "body_goal": item.body_goal,
        "work_start": _minute_label(item.work_start_minutes),
        "work_end": _minute_label(item.work_end_minutes),
        "commute_minutes": item.commute_minutes,
        "preferred_wake": _minute_label(item.preferred_wake_minutes),
        "desired_sleep_hours": item.desired_sleep_hours,
        "hidden_cards": _hidden_cards(item),
        "available_cards": sorted(CARD_IDS),
    }


def _parse_clock(value: str | None) -> int | None:
    if not value:
        return None
    try:
        hour, minute = (int(part) for part in value.split(":", 1))
    except (ValueError, AttributeError):
        raise ValueError("Times must use 24-hour HH:MM format.")
    if hour not in range(24) or minute not in range(60):
        raise ValueError("Times must use 24-hour HH:MM format.")
    return hour * 60 + minute


def update_planning_settings(db: Session, user_id: int, payload: dict) -> dict:
    item = get_or_create_planning(db, user_id)
    if "body_goal" in payload and payload["body_goal"] is not None:
        if payload["body_goal"] not in GOALS:
            raise ValueError("Unsupported body goal.")
        item.body_goal = payload["body_goal"]
    for source, target in (("work_start", "work_start_minutes"), ("work_end", "work_end_minutes"), ("preferred_wake", "preferred_wake_minutes")):
        if source in payload:
            setattr(item, target, _parse_clock(payload[source]))
    if "commute_minutes" in payload and payload["commute_minutes"] is not None:
        item.commute_minutes = max(0, min(int(payload["commute_minutes"]), 240))
    if "desired_sleep_hours" in payload and payload["desired_sleep_hours"] is not None:
        item.desired_sleep_hours = max(5.0, min(float(payload["desired_sleep_hours"]), 10.0))
    if "hidden_cards" in payload and payload["hidden_cards"] is not None:
        hidden = [value for value in payload["hidden_cards"] if value in CARD_IDS]
        item.hidden_cards_json = json.dumps(sorted(set(hidden)))
    db.commit()
    return planning_settings_payload(db, user_id)


def _latest_snapshot(db: Session, user_id: int, end: date) -> HealthSnapshot | None:
    return db.execute(
        select(HealthSnapshot)
        .where(HealthSnapshot.user_id == user_id, HealthSnapshot.date <= end)
        .order_by(HealthSnapshot.date.desc())
        .limit(1)
    ).scalar_one_or_none()


def _recent_workouts(db: Session, user_id: int, end: date, days: int = 7) -> list[Workout]:
    return list(db.execute(
        select(Workout)
        .where(Workout.user_id == user_id, Workout.activity_date >= end - timedelta(days=days - 1), Workout.activity_date <= end)
        .order_by(Workout.activity_date.desc())
    ).scalars().all())


def _activity_kind(activity_type: str | None) -> str:
    value = (activity_type or "").lower()
    if any(word in value for word in ("run", "trail")):
        return "running"
    if any(word in value for word in ("cycle", "bike", "ride")):
        return "cycling"
    if any(word in value for word in ("strength", "gym", "weight", "resistance")):
        return "strength"
    return "other"


def nutrition_plan(db: Session, user_id: int, end: date) -> dict:
    settings = get_or_create_planning(db, user_id)
    profile = _profile(db, user_id)
    snap = _latest_snapshot(db, user_id, end)
    weight = float(snap.weight_kg) if snap and snap.weight_kg else None
    height = float(profile.height_cm) if profile and profile.height_cm else None
    age = ((end - profile.date_of_birth).days / 365.25) if profile and profile.date_of_birth else None
    if not weight:
        return {
            "status": "needs_weight", "title": "Add your current weight to personalise fuel targets.",
            "goal": settings.body_goal, "protein_g": None, "energy_kcal": None,
            "confidence": "low", "notes": ["Weight is required for a body-mass-based protein target."],
        }

    sex = profile.sex if profile else "unspecified"
    if height and age:
        sex_adjustment = 5 if sex == "male" else -161 if sex == "female" else -78
        bmr = round(10 * weight + 6.25 * height - 5 * age + sex_adjustment)
    else:
        bmr = round(weight * 22)
    workouts = _recent_workouts(db, user_id, end, 1)
    exercise_kcal = float(snap.active_calories or 0) if snap else 0.0
    if not exercise_kcal:
        exercise_kcal = sum(float(workout.calories or 0) for workout in workouts)
    kinds = {_activity_kind(workout.activity_type) for workout in workouts}
    duration = sum(float(workout.duration_minutes or 0) for workout in workouts)

    multipliers = {
        "maintain": (1.4, 1.8, 0),
        "lose_weight": (1.8, 2.2, -300),
        "gain_weight": (1.6, 2.0, 250),
        "gain_muscle": (1.6, 2.2, 150),
        "lose_fat": (1.8, 2.4, -300),
    }
    low, high, energy_adjustment = multipliers[settings.body_goal]
    if "strength" in kinds:
        low, high = max(low, 1.7), min(2.4, high + 0.1)
    if ("running" in kinds or "cycling" in kinds) and duration >= 60:
        low, high = max(low, 1.5), min(2.4, high + 0.1)
    protein_low, protein_high = round(weight * low), round(weight * high)
    energy = round(bmr * 1.25 + exercise_kcal + energy_adjustment)
    activity_note = "rest / low-activity day"
    if kinds:
        activity_note = f"{', '.join(sorted(kinds))} session{'s' if len(workouts) != 1 else ''}"
    return {
        "status": "ready", "goal": settings.body_goal, "weight_kg": round(weight, 1),
        "protein_g": {"low": protein_low, "high": protein_high, "midpoint": round((protein_low + protein_high) / 2)},
        "energy_kcal": {"estimate": energy, "bmr": bmr, "activity_kcal": round(exercise_kcal), "goal_adjustment": energy_adjustment},
        "today_activity": {"label": activity_note, "duration_minutes": round(duration), "types": sorted(kinds)},
        "confidence": "medium" if height and age and (snap.active_calories if snap else None) is not None else "low",
        "notes": [
            "Protein is a body-mass and goal-based daily range; workout type changes the upper end.",
            "Energy is an estimate from BMR, Garmin activity calories when available, and your selected goal. It is not a medical prescription.",
        ],
    }


def sleep_schedule(db: Session, user_id: int, end: date, days: int = 90) -> dict:
    settings = get_or_create_planning(db, user_id)
    snaps = list(db.execute(
        select(HealthSnapshot)
        .where(HealthSnapshot.user_id == user_id, HealthSnapshot.date >= end - timedelta(days=days - 1), HealthSnapshot.date <= end)
        .order_by(HealthSnapshot.date.asc())
    ).scalars().all())
    samples = [(snap, _sleep_clock_minute(snap.sleep_start_local), _time_to_minute(snap.sleep_end_local)) for snap in snaps]
    valid = [(snap, bed, wake) for snap, bed, wake in samples if snap.sleep_score is not None and bed is not None and wake is not None]
    best: list[tuple[HealthSnapshot, int, int]] = []
    if valid:
        score_cutoff = sorted(float(snap.sleep_score) for snap, _, _ in valid)[max(0, int(len(valid) * 0.75) - 1)]
        best = [(snap, bed, wake) for snap, bed, wake in valid if float(snap.sleep_score) >= score_cutoff]
    ideal_bed = round(median([bed for _, bed, _ in best])) if best else None
    ideal_wake = round(median([wake for _, _, wake in best])) if best else None
    preferred_wake = settings.preferred_wake_minutes or ideal_wake
    desired_bed = ((preferred_wake - round(settings.desired_sleep_hours * 60)) + 24 * 60) % (24 * 60) if preferred_wake is not None else ideal_bed
    wind_down = ((desired_bed - 60) + 24 * 60) % (24 * 60) if desired_bed is not None else None
    work_bound = None
    if settings.work_start_minutes is not None:
        morning = (settings.work_start_minutes - int(settings.commute_minutes or 0) - 45) % (24 * 60)
        work_bound = _minute_label(morning)
    return {
        "status": "ready" if valid else "needs_history",
        "ideal_bedtime": _minute_label(ideal_bed),
        "ideal_wake_time": _minute_label(ideal_wake),
        "target_bedtime": _minute_label(desired_bed),
        "wind_down_start": _minute_label(wind_down),
        "latest_practical_wake": work_bound,
        "sample_nights": len(valid),
        "confidence": "high" if len(valid) >= 45 else "medium" if len(valid) >= 15 else "low",
        "notes": [
            "Personal best timing uses the upper quartile of your recorded sleep scores, not a generic bedtime.",
            "Schedule targets use your preferred wake time and desired sleep duration when supplied.",
        ],
    }


def sleep_explorer(db: Session, user_id: int, end: date, days: int, bedtime_from: int | None, bedtime_to: int | None, activity_kind: str | None, min_duration: int | None) -> dict:
    start = end - timedelta(days=days - 1)
    snaps = list(db.execute(
        select(HealthSnapshot)
        .where(HealthSnapshot.user_id == user_id, HealthSnapshot.date >= start, HealthSnapshot.date <= end)
        .order_by(HealthSnapshot.date.asc())
    ).scalars().all())
    workouts = _recent_workouts(db, user_id, end, days)
    workouts_by_date: dict[date, list[Workout]] = defaultdict(list)
    for workout in workouts:
        workouts_by_date[workout.activity_date].append(workout)
    points = []
    for snap in snaps:
        bedtime = _sleep_clock_minute(snap.sleep_start_local)
        before_sleep_workouts = workouts_by_date.get(snap.date - timedelta(days=1), []) + workouts_by_date.get(snap.date, [])
        matching = [workout for workout in before_sleep_workouts if (not activity_kind or _activity_kind(workout.activity_type) == activity_kind) and (not min_duration or float(workout.duration_minutes or 0) >= min_duration)]
        if bedtime_from is not None and (bedtime is None or bedtime < bedtime_from):
            continue
        if bedtime_to is not None and (bedtime is None or bedtime > bedtime_to):
            continue
        if activity_kind and not matching:
            continue
        points.append({
            "date": snap.date.isoformat(), "sleep_score": snap.sleep_score, "bedtime": _minute_label(bedtime),
            "wake_time": _minute_label(_time_to_minute(snap.sleep_end_local)), "deep_minutes": snap.sleep_deep_minutes,
            "rem_minutes": snap.sleep_rem_minutes, "workout_types": sorted({_activity_kind(item.activity_type) for item in matching}),
            "workout_duration_minutes": round(sum(float(item.duration_minutes or 0) for item in matching)),
            "workout_average_hr": round(mean([float(item.average_hr) for item in matching if item.average_hr is not None])) if any(item.average_hr is not None for item in matching) else None,
        })
    scored = [float(point["sleep_score"]) for point in points if point["sleep_score"] is not None]
    return {
        "range_days": days, "filters": {"bedtime_from": _minute_label(bedtime_from), "bedtime_to": _minute_label(bedtime_to), "activity_kind": activity_kind, "min_duration": min_duration},
        "points": points, "summary": {"nights": len(points), "average_sleep_score": round(mean(scored), 1) if scored else None, "confidence": "high" if len(scored) >= 20 else "medium" if len(scored) >= 8 else "low"},
    }


def _race_prediction(workouts: list[Workout], kind: str, distance_km: float, exponent: float) -> dict:
    relevant = [workout for workout in workouts if _activity_kind(workout.activity_type) == kind and workout.distance_km and workout.duration_minutes and workout.distance_km >= 1]
    estimates = []
    for workout in relevant:
        seconds = float(workout.duration_minutes) * 60
        equivalent = seconds * pow(distance_km / float(workout.distance_km), exponent)
        estimates.append(equivalent)
    if not estimates:
        return {"distance_km": distance_km, "estimate_seconds": None, "range_seconds": None, "confidence": "low"}
    best = sorted(estimates)[: min(3, len(estimates))]
    estimate = median(best)
    variation = 0.035 if len(relevant) >= 6 else 0.07
    return {
        "distance_km": distance_km, "estimate_seconds": round(estimate),
        "range_seconds": [round(estimate * (1 - variation)), round(estimate * (1 + variation))],
        "confidence": "high" if len(relevant) >= 10 else "medium" if len(relevant) >= 4 else "low",
    }


def fitness_predictions(db: Session, user_id: int, end: date) -> dict:
    workouts = _recent_workouts(db, user_id, end, 90)
    running = [_race_prediction(workouts, "running", distance, 1.06) for distance in (5, 10, 21.0975, 42.195)]
    cycling = [_race_prediction(workouts, "cycling", distance, 1.04) for distance in (20, 40, 100)]
    counts = defaultdict(int)
    for workout in workouts:
        counts[_activity_kind(workout.activity_type)] += 1
    latest = _latest_snapshot(db, user_id, end)
    vo2max = float(latest.vo2max) if latest and latest.vo2max is not None else None
    hr_values = [float(workout.average_hr) for workout in workouts if workout.average_hr is not None]
    running_sessions_per_week = counts["running"] / (90 / 7)
    comparable_running = sum(1 for item in running if item["estimate_seconds"] is not None)
    improvement = None
    decline = None
    if comparable_running:
        improvement_low, improvement_high = (1, 3) if running_sessions_per_week < 2.5 else (0.5, 2)
        improvement = {
            "window_days": 42,
            "change_pct": [improvement_low, improvement_high],
            "condition": "Maintain two easy sessions and one appropriately hard running session each week, only while recovery supports it.",
        }
        decline = {
            "window_days": 28,
            "change_pct": [-4, -1],
            "condition": "No comparable running sessions. This is a planning range based on typical detraining direction, not a promise.",
        }
    scenario = {
        "title": "Consistency is the clearest lever in your current running history." if comparable_running else "Build consistency before chasing a faster forecast.",
        "detail": "Forge bases the estimate on comparable distance and duration; heart rate and available VO2 Max are shown as context while manual perceived effort is still unavailable." if comparable_running else "A scenario appears once Forge has comparable sessions. It models a range, not a guaranteed improvement.",
        "confidence": "low" if not any(item["estimate_seconds"] for item in running + cycling) else "medium",
        "improvement": improvement,
        "decline": decline,
    }
    return {
        "window_days": 90, "sessions": dict(counts), "running": running, "cycling": cycling,
        "scenario": scenario, "inputs": {"vo2max": vo2max, "mean_workout_hr": round(mean(hr_values)) if hr_values else None, "rpe": None},
        "notes": [
            "Forecasts use comparable Garmin distance and duration. Workout heart rate and available VO2 Max provide context; perceived effort is not inferred and needs a future manual activity log.",
            "Decline estimates are conservative planning ranges rather than a prediction of what will happen to you.",
        ],
    }
