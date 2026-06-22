"""Real Garmin Connect sync — uses saved session tokens, no login needed."""
from __future__ import annotations

import json
import logging
import secrets
import threading
from datetime import date, datetime, timedelta
from statistics import mean, pstdev
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.account import SyncJob, Workout
from app.models.health import HealthSnapshot
from app.services.profile import actual_age_years
from app.services.scoring import compute_fitness_age, compute_biological_age
from app.services.connections import (
    ConnectionSecurityError,
    decrypt_token_blob,
    get_connection,
    upsert_garmin_connection,
)

log = logging.getLogger(__name__)

def _reset_client(user_id: int) -> None:
    _user_client_cache.pop(user_id, None)


_user_client_cache: dict[int, Any] = {}
_pending_mfa: dict[str, dict[str, Any]] = {}
_mfa_lock = threading.Lock()
_MFA_TTL_SECONDS = 10 * 60


def _connection_client(db: Session, user_id: int) -> Any:
    cached = _user_client_cache.get(user_id)
    if cached is not None:
        return cached
    connection = get_connection(db, user_id)
    if not connection or connection.status != "connected" or not connection.encrypted_token_blob:
        raise RuntimeError("Garmin is not connected for this Forge account.")
    try:
        token_blob = decrypt_token_blob(connection.encrypted_token_blob)
    except ConnectionSecurityError as exc:
        connection.status = "needs_reconnect"
        connection.last_error = "Saved Garmin session could not be opened. Reconnect Garmin."
        db.commit()
        raise RuntimeError(connection.last_error) from exc

    from garminconnect import Garmin
    client = Garmin()
    try:
        # Token blobs are serialized JSON, not file paths. Loading directly
        # avoids the library's convenience heuristic that treats short values
        # as a tokenstore filename.
        client.client.loads(token_blob)
        client._load_profile_and_settings()
    except Exception as exc:
        connection.status = "needs_reconnect"
        connection.last_error = "Saved Garmin session has expired. Reconnect Garmin."
        db.commit()
        raise RuntimeError(connection.last_error) from exc
    _user_client_cache[user_id] = client
    return client


def _finish_connection(db: Session, user_id: int, client: Any) -> dict[str, Any]:
    subject = getattr(client, "display_name", None) or getattr(client, "full_name", None) or "Garmin account"
    connection = upsert_garmin_connection(
        db,
        user_id=user_id,
        token_blob=client.client.dumps(),
        external_subject=subject,
    )
    _user_client_cache[user_id] = client
    return {
        "status": "connected",
        "connected": True,
        "account": connection.external_subject,
        "message": "Garmin connected. Your password was not stored.",
    }


def connect_user_garmin(db: Session, user_id: int, email: str, password: str) -> dict[str, Any]:
    """Exchange Garmin credentials for an encrypted per-user session token."""
    from garminconnect import (
        Garmin,
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    )

    client = Garmin(email, password, return_on_mfa=True)
    try:
        mfa_status, _ = client.login()
    except GarminConnectTooManyRequestsError as exc:
        log.warning("Garmin rate-limited a connection attempt for Forge user %s", user_id)
        raise RuntimeError("Garmin temporarily rate-limited this connection. Wait a few minutes, then try again.") from exc
    except GarminConnectAuthenticationError as exc:
        log.info("Garmin authentication rejected for Forge user %s", user_id)
        raise RuntimeError(
            "Garmin rejected the sign-in. First sign in at connect.garmin.com and complete any security prompts, then retry."
        ) from exc
    except GarminConnectConnectionError as exc:
        log.warning("Garmin connection failed for Forge user %s: %s", user_id, type(exc).__name__)
        raise RuntimeError(
            "Garmin blocked or could not complete this automated sign-in. Check Garmin Connect in a browser, complete any CAPTCHA or device verification, then retry."
        ) from exc
    except Exception as exc:
        log.warning("Unexpected Garmin connection failure for Forge user %s: %s", user_id, type(exc).__name__)
        raise RuntimeError("Garmin sign-in failed before a session could be created. Retry after checking Garmin Connect in a browser.") from exc

    if mfa_status == "needs_mfa":
        challenge_id = secrets.token_urlsafe(32)
        with _mfa_lock:
            _pending_mfa[challenge_id] = {
                "user_id": user_id,
                "client": client,
                "expires_at": datetime.utcnow() + timedelta(seconds=_MFA_TTL_SECONDS),
            }
        return {
            "status": "mfa_required",
            "connected": False,
            "challenge_id": challenge_id,
            "mfa_method": "verification code",
            "message": "Garmin sent a verification code. Enter it to finish connecting.",
        }
    return _finish_connection(db, user_id, client)


def complete_user_garmin_mfa(db: Session, user_id: int, challenge_id: str, code: str) -> dict[str, Any]:
    with _mfa_lock:
        pending = _pending_mfa.pop(challenge_id, None)
    if not pending or pending["user_id"] != user_id or pending["expires_at"] < datetime.utcnow():
        raise RuntimeError("This Garmin verification challenge expired. Connect Garmin again.")
    try:
        pending["client"].client.resume_login(None, code)
        pending["client"]._load_profile_and_settings()
    except Exception as exc:
        log.info("Garmin MFA rejected for Forge user %s", user_id)
        raise RuntimeError("Garmin could not verify that code. Connect Garmin again and request a new code.") from exc
    return _finish_connection(db, user_id, pending["client"])


def _safe(d: dict, *keys, default=None):
    v = d
    for k in keys:
        if not isinstance(v, dict):
            return default
        v = v.get(k, default)
        if v is None:
            return default
    return v


def _find_number(obj: Any, names: set[str]) -> float | None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in names and isinstance(value, (int, float)) and value not in (-1, 0):
                return float(value)
            found = _find_number(value, names)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_number(item, names)
            if found is not None:
                return found
    return None


def _minutes_from_seconds_or_minutes(value: float | int | None) -> int | None:
    if value in (None, 0):
        return None
    if isinstance(value, dict):
        value = _find_number(value, {
            "value",
            "minutes",
            "minute",
            "seconds",
            "second",
            "sleepNeed",
            "sleepNeedMinutes",
            "sleepNeedSeconds",
        })
        if value in (None, 0):
            return None
    if not isinstance(value, (int, float, str)):
        return None
    number = float(value)
    if number > 24 * 60:
        number = number / 60
    return int(number)


def _minutes_from_seconds(value: float | int | str | None) -> int | None:
    if value in (None, 0):
        return None
    if not isinstance(value, (int, float, str)):
        return None
    number = float(value)
    # Garmin timestamps are milliseconds, but duration fields can occasionally
    # arrive as ms from alternate endpoints. Keep seconds explicit here.
    if number > 10_000_000:
        number = number / 1000
    return int(number / 60)


def _local_timestamp(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, str) and "-" in value:
        return value
    if isinstance(value, (int, float)):
        number = float(value)
        if number > 10_000_000:
            number = number / 1000
        try:
            return datetime.fromtimestamp(number).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    return None


def _fetch_vo2max(client: Any, ds: str, raw: dict[str, Any]) -> float | None:
    existing = _find_number(raw, {"vo2MaxValue", "vO2MaxPreciseValue", "generic", "cycling", "running", "vo2Max"})
    if existing is not None:
        return round(existing, 1)
    try:
        data = client.get_max_metrics(ds)
        raw["max_metrics"] = data
        found = _find_number(data, {"vo2MaxValue", "vO2MaxPreciseValue", "vo2Max", "generic", "cycling", "running"})
        if found is not None:
            return round(found, 1)
    except Exception as e:
        log.debug("Garmin max-metrics VO2 lookup failed for %s: %s", ds, e)
    endpoints = [
        f"/biometric-service/biometric/maxMetrics/{ds}",
        f"/userprofile-service/userprofile/personal-information/vo2max/{ds}",
    ]
    for endpoint in endpoints:
        try:
            connectapi = (
                getattr(getattr(client, "client", None), "connectapi", None)
                or getattr(getattr(client, "garth", None), "connectapi", None)
                or getattr(client, "connectapi", None)
            )
            if not connectapi:
                continue
            data = connectapi(endpoint)
            raw[f"vo2:{endpoint}"] = data
            found = _find_number(data, {"vo2MaxValue", "vO2MaxPreciseValue", "vo2Max", "generic", "cycling", "running"})
            if found is not None:
                return round(found, 1)
        except Exception as e:
            log.debug("VO2 lookup failed for %s: %s", endpoint, e)
    return None


def _activity_start_date(activity: dict[str, Any]) -> str | None:
    value = activity.get("startTimeLocal") or activity.get("startTimeGMT") or activity.get("beginTimestamp")
    if not value:
        return None
    if isinstance(value, str):
        return value[:10]
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000:
            timestamp = timestamp / 1000
        try:
            return datetime.fromtimestamp(timestamp).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    return None


def _fetch_activities_for_date(client: Any, ds: str, raw: dict[str, Any]) -> list[dict[str, Any]]:
    activities: list[dict[str, Any]] = []
    try:
        data = client.get_activities_by_date(ds, ds) or []
        raw["activities"] = data
        if isinstance(data, list):
            activities = [a for a in data if isinstance(a, dict) and _activity_start_date(a) == ds]
    except Exception as e:
        log.debug("Activity lookup failed for %s: %s", ds, e)

    if activities:
        return activities

    try:
        data = client.get_activities_fordate(ds)
        raw["activities_for_date"] = data
        payload = _safe(data, "ActivitiesForDay", "payload") or []
        if isinstance(payload, list):
            activities = [a for a in payload if isinstance(a, dict)]
    except Exception as e:
        log.debug("Activity for-date lookup failed for %s: %s", ds, e)
    return activities


def _activity_number(activity: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = activity.get(key)
        if isinstance(value, (int, float)) and value >= 0:
            return float(value)
    return None


def _activity_type(activity: dict[str, Any]) -> str | None:
    raw_type = activity.get("activityType")
    if isinstance(raw_type, dict):
        raw_type = raw_type.get("typeKey") or raw_type.get("typeName") or raw_type.get("displayName")
    if raw_type is None:
        raw_type = activity.get("activityTypeName") or activity.get("activityName")
    return str(raw_type).strip()[:80] if raw_type else None


def _persist_activities(db: Session, user_id: int, activity_date: date, activities: list[dict[str, Any]]) -> None:
    """Persist only activity fields needed for personal timing/intensity analysis."""
    for activity in activities:
        provider_id = activity.get("activityId") or activity.get("activityUUID")
        if provider_id is None:
            continue
        workout = db.execute(
            select(Workout).where(
                Workout.user_id == user_id,
                Workout.provider_activity_id == str(provider_id),
            )
        ).scalar_one_or_none()
        if workout is None:
            workout = Workout(user_id=user_id, provider_activity_id=str(provider_id), activity_date=activity_date)
            db.add(workout)
        workout.start_local = str(activity.get("startTimeLocal") or activity.get("startTimeGMT") or "")[:40] or None
        workout.activity_type = _activity_type(activity)
        duration = _activity_number(activity, "duration", "elapsedDuration", "movingDuration")
        workout.duration_minutes = round(duration / 60, 1) if duration and duration > 180 else duration
        distance = _activity_number(activity, "distance", "distanceMeters")
        workout.distance_km = round(distance / 1000, 2) if distance and distance > 100 else distance
        workout.average_hr = _activity_number(activity, "averageHR", "avgHR")
        workout.max_hr = _activity_number(activity, "maxHR")
        workout.calories = _activity_number(activity, "calories", "activeKilocalories")


def _activity_vo2max(activities: list[dict[str, Any]]) -> float | None:
    values = []
    for activity in activities:
        value = (
            activity.get("vO2MaxValue")
            or activity.get("vo2MaxValue")
            or activity.get("vO2MaxPreciseValue")
            or activity.get("vo2MaxPreciseValue")
        )
        if isinstance(value, (int, float)) and value > 0:
            values.append(float(value))
    return round(values[-1], 1) if values else None


def _daily_hr_samples(data: Any) -> list[tuple[int, float]]:
    payload = data.get("payload") if isinstance(data, dict) and isinstance(data.get("payload"), dict) else data
    values = payload.get("heartRateValues") if isinstance(payload, dict) else None
    samples: list[tuple[int, float]] = []
    if not isinstance(values, list):
        return samples
    for item in values:
        if not isinstance(item, list) or len(item) < 2:
            continue
        ts, hr = item[0], item[1]
        if isinstance(ts, (int, float)) and isinstance(hr, (int, float)) and 30 <= hr <= 230:
            samples.append((int(ts), float(hr)))
    return samples


def _activity_hr_samples(details: dict[str, Any], activity: dict[str, Any]) -> list[tuple[int, float]]:
    rows = [
        row.get("metrics")
        for row in (details.get("activityDetailMetrics") or [])
        if isinstance(row, dict) and isinstance(row.get("metrics"), list)
    ]
    if len(rows) < 2:
        return []

    max_len = max(len(row) for row in rows)
    timestamp_index = None
    best_ts_count = 0
    for idx in range(max_len):
        count = sum(1 for row in rows if idx < len(row) and isinstance(row[idx], (int, float)) and row[idx] > 10_000_000)
        if count > best_ts_count:
            timestamp_index = idx
            best_ts_count = count
    if timestamp_index is None:
        return []

    summary_max = activity.get("maxHR")
    summary_avg = activity.get("averageHR")
    candidates: list[tuple[float, int]] = []
    for idx in range(max_len):
        if idx == timestamp_index:
            continue
        values = [float(row[idx]) for row in rows if idx < len(row) and isinstance(row[idx], (int, float)) and 30 <= float(row[idx]) <= 230]
        if len(values) < max(10, len(rows) * 0.5):
            continue
        if max(values) < 80 or (len(values) > 1 and pstdev(values) < 3):
            continue
        score = 0.0
        if isinstance(summary_max, (int, float)):
            score += abs(max(values) - float(summary_max))
        if isinstance(summary_avg, (int, float)):
            score += abs(mean(values) - float(summary_avg)) * 0.35
        candidates.append((score, idx))
    if not candidates:
        return []

    _, hr_index = min(candidates, key=lambda item: item[0])
    samples: list[tuple[int, float]] = []
    for row in rows:
        if timestamp_index >= len(row) or hr_index >= len(row):
            continue
        ts = row[timestamp_index]
        hr = row[hr_index]
        if isinstance(ts, (int, float)) and isinstance(hr, (int, float)) and 30 <= hr <= 230:
            samples.append((int(ts), float(hr)))
    return sorted(samples)


def _nearest_hr_after(samples: list[tuple[int, float]], target_ms: int, window_ms: int = 180_000) -> float | None:
    candidates = [(abs(ts - target_ms), hr) for ts, hr in samples if target_ms - 30_000 <= ts <= target_ms + window_ms]
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[0])[1]


def _fetch_hr_recovery(client: Any, ds: str, activities: list[dict[str, Any]], raw: dict[str, Any]) -> float | None:
    direct_keys = {"heartRateRecovery", "hrRecovery", "hrRecoveryDelta", "heartRateRecoveryDelta"}
    for activity in activities:
        direct = _find_number(activity, direct_keys)
        if direct is not None:
            return round(direct, 1)

    try:
        daily_hr = client.get_heart_rates(ds)
        raw["daily_hr"] = daily_hr
        daily_samples = _daily_hr_samples(daily_hr)
    except Exception as e:
        log.debug("Daily HR lookup failed for %s: %s", ds, e)
        daily_samples = []

    best_drop: float | None = None
    for activity in activities:
        activity_id = activity.get("activityId")
        if not activity_id:
            continue
        try:
            details = client.get_activity_details(activity_id)
            raw[f"activity_details:{activity_id}"] = {"keys": list(details.keys())[:20]}
        except Exception as e:
            log.debug("Activity detail lookup failed for %s: %s", activity_id, e)
            continue

        samples = _activity_hr_samples(details, activity)
        if len(samples) < 2:
            continue
        end_ts, end_hr = samples[-1]
        recovery_hr = _nearest_hr_after(daily_samples, end_ts + 60_000) if daily_samples else None
        if recovery_hr is None:
            # Fallback: use the lowest recorded HR in the final two minutes of the
            # activity. It is less ideal than post-workout HR, but still avoids a
            # silent empty card when Garmin omits a formal HRR field.
            tail = [hr for ts, hr in samples if end_ts - 120_000 <= ts <= end_ts]
            recovery_hr = min(tail) if tail else None
        if recovery_hr is None:
            continue
        drop = max(0.0, float(end_hr) - float(recovery_hr))
        if best_drop is None or drop > best_drop:
            best_drop = drop
    return round(best_drop, 1) if best_drop is not None else None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _score_higher(value: float | None, low: float, high: float) -> float | None:
    if value is None:
        return None
    return _clamp((value - low) / (high - low) * 100, 0, 100)


def _score_lower(value: float | None, low: float, high: float) -> float | None:
    if value is None:
        return None
    return _clamp((high - value) / (high - low) * 100, 0, 100)


def _weighted(parts: list[tuple[float | None, float]]) -> float | None:
    present = [(value, weight) for value, weight in parts if value is not None]
    if not present:
        return None
    total = sum(weight for _, weight in present)
    return round(sum(value * weight for value, weight in present) / total, 1)


def _derive_scores(db: Session, snap: HealthSnapshot) -> None:
    """Fill Forge-derived metrics when Garmin does not provide direct values."""
    hrv_score = None
    if snap.hrv_ms is not None and snap.hrv_baseline_ms:
        hrv_score = _clamp((snap.hrv_ms / snap.hrv_baseline_ms) * 50, 0, 100)

    rhr_score = None
    if snap.rhr_bpm is not None and snap.rhr_baseline_bpm is not None:
        rhr_score = _clamp(70 - (snap.rhr_bpm - snap.rhr_baseline_bpm) * 6, 0, 100)

    stress_score = _score_lower(snap.stress, 20, 70)
    body_battery_score = _score_higher(snap.body_battery, 20, 90)

    snap.recovery = _weighted([
        (snap.sleep_score, 0.35),
        (hrv_score, 0.25),
        (rhr_score, 0.18),
        (stress_score, 0.12),
        (body_battery_score, 0.10),
    ])

    moderate = snap.moderate_intensity_min or 0
    vigorous = snap.vigorous_intensity_min or 0
    active = snap.active_minutes or 0
    steps = snap.steps or 0
    passive_load = min(6.0, steps / 2500)
    active_load = active * 0.045 + moderate * 0.09 + vigorous * 0.18
    snap.strain = round(_clamp(passive_load + active_load, 0, 30), 1)

    if snap.recovery is not None:
        if snap.recovery >= 75:
            snap.target_strain = 14
        elif snap.recovery >= 60:
            snap.target_strain = 11
        elif snap.recovery >= 45:
            snap.target_strain = 8
        else:
            snap.target_strain = 5

    if snap.cardio_load is None:
        snap.cardio_load = round(active * 1.0 + moderate * 1.5 + vigorous * 3.0, 1)

    prior = db.query(HealthSnapshot).filter(
        HealthSnapshot.user_id == snap.user_id,
        HealthSnapshot.date < snap.date,
        HealthSnapshot.date >= snap.date - timedelta(days=42),
        HealthSnapshot.cardio_load.isnot(None),
    ).order_by(HealthSnapshot.date.asc()).all()
    loads = [float(row.cardio_load) for row in prior if row.cardio_load is not None] + ([float(snap.cardio_load)] if snap.cardio_load is not None else [])
    if len(loads) >= 7:
        acute = mean(loads[-7:])
        chronic = mean(loads[-42:])
        snap.load_balance = round(acute / chronic, 2) if chronic else None

    if snap.readiness is None:
        strain_penalty = min(20, (snap.strain or 0) * 0.8)
        snap.readiness = round(_clamp((snap.recovery or 50) - strain_penalty + 10, 0, 100), 1)


def sync_date(db: Session, target_date: date, user_id: int, client: Any | None = None) -> HealthSnapshot:
    client = client or _connection_client(db, user_id)
    ds = target_date.isoformat()
    raw: dict[str, Any] = {}

    # Daily summary
    try:
        summary = client.get_stats(ds)
        raw["summary"] = summary
    except Exception as e:
        log.warning("Failed to get stats for %s: %s", ds, e)
        summary = {}

    # Sleep
    try:
        sleep = client.get_sleep_data(ds)
        raw["sleep"] = sleep
    except Exception as e:
        log.warning("Failed to get sleep for %s: %s", ds, e)
        sleep = {}

    # HRV
    try:
        hrv = client.get_hrv_data(ds)
        raw["hrv"] = hrv
    except Exception as e:
        log.warning("Failed to get HRV for %s: %s", ds, e)
        hrv = {}

    # Stress
    try:
        stress_data = client.get_stress_data(ds)
        raw["stress"] = stress_data
    except Exception as e:
        log.warning("Failed to get stress for %s: %s", ds, e)
        stress_data = {}

    # SpO2
    try:
        spo2_data = client.get_spo2_data(ds)
        raw["spo2"] = spo2_data
    except Exception as e:
        log.warning("Failed to get SpO2 for %s: %s", ds, e)
        spo2_data = {}

    # Respiration
    try:
        resp_data = client.get_respiration_data(ds)
        raw["respiration"] = resp_data
    except Exception as e:
        log.warning("Failed to get respiration for %s: %s", ds, e)
        resp_data = {}

    # Body composition
    try:
        body = client.get_body_composition(ds)
        raw["body"] = body
    except Exception as e:
        log.warning("Failed to get body composition for %s: %s", ds, e)
        body = {}

    # Activities are needed for sparse metrics Garmin does not put in daily stats:
    # VO2 Max is attached to qualifying workouts, and HR Recovery comes from
    # workout/post-workout heart-rate samples.
    activities = _fetch_activities_for_date(client, ds, raw)
    _persist_activities(db, user_id, target_date, activities)

    # VO2 max updates sparsely, so fetch it separately from Garmin's biometric/user profile endpoints.
    vo2max = _activity_vo2max(activities) or _fetch_vo2max(client, ds, raw)
    hr_recovery = _fetch_hr_recovery(client, ds, activities, raw)

    # Upsert snapshot
    snap = db.query(HealthSnapshot).filter(
        HealthSnapshot.user_id == user_id,
        HealthSnapshot.date == target_date,
    ).first()
    if not snap:
        snap = HealthSnapshot(user_id=user_id, date=target_date)
        db.add(snap)

    # --- Parse summary ---
    snap.steps = _safe(summary, "totalSteps")
    snap.steps_goal = _safe(summary, "dailyStepGoal")
    snap.active_calories = _safe(summary, "activeKilocalories")
    snap.total_calories = _safe(summary, "burnedKilocalories") or _safe(summary, "totalKilocalories")
    snap.active_minutes = _safe(summary, "highlyActiveSeconds", default=0)
    if snap.active_minutes:
        snap.active_minutes = snap.active_minutes // 60
    snap.floors_climbed = _safe(summary, "floorsAscended")
    snap.rhr_bpm = _safe(summary, "restingHeartRate")
    snap.max_hr = _safe(summary, "maxHeartRate")
    snap.hr_recovery = hr_recovery
    stress_value = _safe(summary, "averageStressLevel")
    snap.stress = None if stress_value == -1 else stress_value
    snap.body_battery = _safe(summary, "bodyBatteryMostRecentValue")
    snap.moderate_intensity_min = (_safe(summary, "moderateIntensityMinutes") or 0)
    snap.vigorous_intensity_min = (_safe(summary, "vigorousIntensityMinutes") or 0)
    snap.distance_km = (_safe(summary, "totalDistanceMeters") or 0) / 1000 or None
    snap.vo2max = vo2max or _find_number(summary, {"vo2MaxValue", "vO2MaxPreciseValue", "vo2Max"})

    # Stress durations
    if isinstance(stress_data, dict):
        vals = stress_data.get("stressValuesArray") or []
        rest = low = med = high = 0
        valid_stress_values: list[float] = []
        for pair in vals:
            if not pair or len(pair) < 2:
                continue
            lvl = pair[1] if pair[1] is not None else -1
            if lvl < 0:
                rest += 1
            elif lvl < 26:
                valid_stress_values.append(float(lvl))
                low += 1
            elif lvl < 51:
                valid_stress_values.append(float(lvl))
                med += 1
            else:
                valid_stress_values.append(float(lvl))
                high += 1
        snap.stress_duration_rest_min = rest
        snap.stress_duration_low_min = low
        snap.stress_duration_medium_min = med
        snap.stress_duration_high_min = high
        if snap.stress is None and valid_stress_values:
            snap.stress = round(mean(valid_stress_values), 1)

    # --- Parse sleep ---
    daily_sleep = _safe(sleep, "dailySleepDTO") or {}
    snap.sleep_score = _safe(daily_sleep, "sleepScores", "overall", "value") or _safe(daily_sleep, "sleepScore") or _find_number(sleep, {"overallSleepScore", "sleepScore"})
    snap.sleep_minutes = _minutes_from_seconds(_safe(daily_sleep, "sleepTimeSeconds")) or _minutes_from_seconds_or_minutes(_safe(daily_sleep, "sleepTimeMinutes"))
    snap.sleep_deep_minutes = _minutes_from_seconds(_safe(daily_sleep, "deepSleepSeconds")) or _minutes_from_seconds_or_minutes(_safe(daily_sleep, "deepSleepMinutes"))
    snap.sleep_rem_minutes = _minutes_from_seconds(_safe(daily_sleep, "remSleepSeconds")) or _minutes_from_seconds_or_minutes(_safe(daily_sleep, "remSleepMinutes"))
    snap.sleep_light_minutes = _minutes_from_seconds(_safe(daily_sleep, "lightSleepSeconds")) or _minutes_from_seconds_or_minutes(_safe(daily_sleep, "lightSleepMinutes"))
    snap.sleep_awake_minutes = _minutes_from_seconds(_safe(daily_sleep, "awakeSleepSeconds")) or _minutes_from_seconds_or_minutes(_safe(daily_sleep, "awakeSleepMinutes"))
    sleep_need = (
        _safe(daily_sleep, "sleepNeed", "actual")
        or _safe(daily_sleep, "sleepNeed", "baseline")
        or _safe(daily_sleep, "sleepNeed", "value")
        or _safe(daily_sleep, "sleepNeed")
    )
    snap.sleep_need_minutes = _minutes_from_seconds_or_minutes(sleep_need)
    snap.sleep_start_local = _local_timestamp(_safe(daily_sleep, "sleepStartTimestampLocal"))
    snap.sleep_end_local = _local_timestamp(_safe(daily_sleep, "sleepEndTimestampLocal"))

    if not snap.sleep_need_minutes and snap.sleep_minutes:
        snap.sleep_need_minutes = 480
    if snap.sleep_need_minutes and snap.sleep_minutes:
        snap.sleep_debt_minutes = max(0, snap.sleep_need_minutes - snap.sleep_minutes)

    snap.nap_minutes = _minutes_from_seconds(_safe(daily_sleep, "napTimeSeconds")) or _minutes_from_seconds_or_minutes(_safe(daily_sleep, "napTimeMinutes"))

    # --- Parse HRV ---
    hrv_summary = _safe(hrv, "hrvSummary") or {}
    snap.hrv_ms = _safe(hrv_summary, "lastNight") or _safe(hrv_summary, "lastNightAvg") or _find_number(hrv, {"lastNight", "lastNightAvg", "weeklyAvg", "hrvValue", "rmssd"})
    snap.hrv_baseline_ms = _safe(hrv_summary, "baseline", "balancedLow") or _safe(hrv_summary, "weeklyAvg") or _find_number(hrv, {"balancedLow", "weeklyAvg", "baselineValue"})
    snap.respiration_sleep = _safe(hrv_summary, "avgBreathingRate")

    # --- Parse SpO2 ---
    if isinstance(spo2_data, dict):
        snap.spo2_avg = _safe(spo2_data, "averageSpO2") or _safe(spo2_data, "avgSpo2")
        snap.spo2_min = _safe(spo2_data, "lowestSpO2") or _safe(spo2_data, "minSpo2")

    # --- Parse respiration ---
    if isinstance(resp_data, dict):
        snap.respiration_avg = _safe(resp_data, "avgWakingRespirationValue") or _safe(resp_data, "avgBreathingRate")

    # --- Parse body composition ---
    body_list = _safe(body, "totalAverage") or body or {}
    if isinstance(body_list, dict):
        snap.weight_kg = _safe(body_list, "weight")
        if snap.weight_kg and snap.weight_kg > 500:
            snap.weight_kg = round(snap.weight_kg / 1000, 2)
        snap.body_fat_pct = _safe(body_list, "bodyFat")
        snap.muscle_mass_kg = (_safe(body_list, "muscleMass") or 0) / 1000 or None
        snap.bone_mass_kg = (_safe(body_list, "boneMass") or 0) / 1000 or None
        snap.bmi = _safe(body_list, "bmi")

    _derive_scores(db, snap)

    # Derived scores
    actual_age = actual_age_years(db, user_id)
    snap.fitness_age, snap.fitness_age_status = compute_fitness_age(snap, actual_age)
    snap.biological_age, snap.biological_age_status = compute_biological_age(snap, actual_age)

    snap.source = "garmin"
    snap.raw_json = json.dumps({"keys": list(summary.keys())[:20]})

    db.commit()
    db.refresh(snap)
    return snap


def sync_today(db: Session, user_id: int) -> dict:
    today = date.today()
    try:
        snap = sync_date(db, today, user_id)
        connection = get_connection(db, user_id)
        if connection:
            connection.last_synced_at = datetime.utcnow()
            connection.last_error = None
            db.commit()
        return {"status": "ok", "date": today.isoformat(), "source": snap.source}
    except RuntimeError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        _reset_client(user_id)
        connection = get_connection(db, user_id)
        if connection:
            connection.last_error = "Sync failed. Retry from Forge."
            db.commit()
        log.exception("Garmin sync failed")
        return {"status": "error", "message": f"Sync failed: {e}"}


def sync_history(
    db: Session,
    user_id: int,
    days: int = 365,
    *,
    refresh_existing: bool = False,
    progress: Callable[[dict[str, Any], date], None] | None = None,
) -> dict:
    today = date.today()
    results = {"synced": 0, "failed": 0, "skipped": 0, "errors": []}
    for i in range(days):
        d = today - timedelta(days=i)
        existing = db.query(HealthSnapshot).filter(
            HealthSnapshot.user_id == user_id,
            HealthSnapshot.date == d,
            HealthSnapshot.source == "garmin",
        ).first()
        if existing and not refresh_existing:
            _derive_scores(db, existing)
            actual_age = actual_age_years(db, user_id)
            existing.fitness_age, existing.fitness_age_status = compute_fitness_age(existing, actual_age)
            existing.biological_age, existing.biological_age_status = compute_biological_age(existing, actual_age)
            db.commit()
            results["skipped"] += 1
            results["completed"] = i + 1
            if progress:
                progress(results, d)
            continue
        try:
            sync_date(db, d, user_id)
            results["synced"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{d}: {e}")
            if results["failed"] > 10:
                results["errors"].append("Too many failures - stopping early")
                break
        results["completed"] = i + 1
        if progress:
            progress(results, d)
    connection = get_connection(db, user_id)
    if connection:
        connection.last_synced_at = datetime.utcnow()
        connection.last_error = None if not results["failed"] else f"{results['failed']} day(s) could not be imported."
        db.commit()
    return results


def job_payload(job: SyncJob) -> dict[str, Any]:
    total = max(job.total_days, 1)
    return {
        "id": job.id,
        "status": job.status,
        "days_requested": job.days_requested,
        "total_days": job.total_days,
        "completed_days": job.completed_days,
        "synced_days": job.synced_days,
        "skipped_days": job.skipped_days,
        "failed_days": job.failed_days,
        "progress_pct": round(job.completed_days / total * 100),
        "current_date": job.current_date.isoformat() if job.current_date else None,
        "error": job.error,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def latest_history_job(db: Session, user_id: int) -> SyncJob | None:
    return db.execute(
        select(SyncJob)
        .where(SyncJob.user_id == user_id, SyncJob.provider == "garmin", SyncJob.kind == "history")
        .order_by(SyncJob.started_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def get_history_job(db: Session, user_id: int, job_id: int) -> SyncJob | None:
    return db.execute(
        select(SyncJob).where(SyncJob.id == job_id, SyncJob.user_id == user_id)
    ).scalar_one_or_none()


def _run_history_job(job_id: int, user_id: int, days: int) -> None:
    db = SessionLocal()
    try:
        job = get_history_job(db, user_id, job_id)
        if not job:
            return
        job.status = "running"
        db.commit()

        def update_progress(result: dict[str, Any], current_day: date) -> None:
            active_job = get_history_job(db, user_id, job_id)
            if not active_job:
                return
            active_job.completed_days = int(result.get("completed", 0))
            active_job.synced_days = int(result.get("synced", 0))
            active_job.skipped_days = int(result.get("skipped", 0))
            active_job.failed_days = int(result.get("failed", 0))
            active_job.current_date = current_day
            db.commit()

        result = sync_history(db, user_id, days, refresh_existing=True, progress=update_progress)
        job = get_history_job(db, user_id, job_id)
        if job:
            job.status = "completed" if result["failed"] == 0 else "completed_with_errors"
            job.completed_days = int(result.get("completed", days))
            job.synced_days = result["synced"]
            job.skipped_days = result["skipped"]
            job.failed_days = result["failed"]
            job.error = "; ".join(result["errors"][:2]) or None
            job.finished_at = datetime.utcnow()
            db.commit()
    except Exception:
        log.exception("Garmin history job %s failed", job_id)
        job = get_history_job(db, user_id, job_id)
        if job:
            job.status = "failed"
            job.error = "History import failed. Retry from Forge."
            job.finished_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


def start_history_sync(db: Session, user_id: int, days: int = 365) -> dict[str, Any]:
    active = db.execute(
        select(SyncJob)
        .where(
            SyncJob.user_id == user_id,
            SyncJob.provider == "garmin",
            SyncJob.kind == "history",
            SyncJob.status.in_(["queued", "running"]),
        )
        .order_by(SyncJob.started_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if active:
        return job_payload(active)

    bounded_days = min(max(days, 1), 365)
    job = SyncJob(user_id=user_id, days_requested=bounded_days, total_days=bounded_days)
    db.add(job)
    db.commit()
    db.refresh(job)
    threading.Thread(target=_run_history_job, args=(job.id, user_id, bounded_days), daemon=True).start()
    return job_payload(job)


def recompute_existing(db: Session, user_id: int) -> dict:
    actual_age = actual_age_years(db, user_id)
    rows = db.query(HealthSnapshot).filter(
        HealthSnapshot.user_id == user_id
    ).order_by(HealthSnapshot.date.asc()).all()
    updated = 0
    for snap in rows:
        _derive_scores(db, snap)
        snap.fitness_age, snap.fitness_age_status = compute_fitness_age(snap, actual_age)
        snap.biological_age, snap.biological_age_status = compute_biological_age(snap, actual_age)
        updated += 1
    db.commit()
    return {"status": "ok", "updated": updated}
