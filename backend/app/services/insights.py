"""Deterministic health history analytics.

This module turns stored HealthSnapshot rows into UI-ready history, flags,
and insight cards. AI can narrate these results, but the numbers come from
here first.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import sqrt
from statistics import mean, pstdev
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.health import HealthSnapshot
from app.services.profile import actual_age_years


@dataclass(frozen=True)
class MetricSpec:
    field: str
    label: str
    unit: str = ""
    higher_is_better: bool = True
    low: float | None = None
    high: float | None = None
    volatility_sensitive: bool = True
    target_range_is_best: bool = False


METRIC_SPECS: dict[str, MetricSpec] = {
    "recovery": MetricSpec("recovery", "Recovery", "", True, 55, 80),
    "readiness": MetricSpec("readiness", "Readiness", "", True, 55, 80),
    "strain": MetricSpec("strain", "Strain", "", True, 5, 15, False, True),
    "target_strain": MetricSpec("target_strain", "Target Strain"),
    "sleep_score": MetricSpec("sleep_score", "Sleep Score", "", True, 65, 85),
    "sleep_hours": MetricSpec("sleep_minutes", "Sleep Hours", "h", True, 7, 9, True, True),
    "deep_sleep": MetricSpec("sleep_deep_minutes", "Deep Sleep", "h", True, 1, 2),
    "rem_sleep": MetricSpec("sleep_rem_minutes", "REM Sleep", "h", True, 1.5, 2.5),
    "light_sleep": MetricSpec("sleep_light_minutes", "Light Sleep", "h", True, None, None, False),
    "awake_time": MetricSpec("sleep_awake_minutes", "Awake Time", "h", False, 0.2, 0.8),
    "sleep_debt": MetricSpec("sleep_debt_minutes", "Sleep Debt", "h", False, 0, 1.5),
    "sleep_need": MetricSpec("sleep_need_minutes", "Sleep Need", "h", False, 7, 9),
    "hrv": MetricSpec("hrv_ms", "HRV", "ms", True),
    "hrv_baseline": MetricSpec("hrv_baseline_ms", "HRV Baseline", "ms", True),
    "rhr": MetricSpec("rhr_bpm", "Resting HR", "bpm", False),
    "rhr_baseline": MetricSpec("rhr_baseline_bpm", "RHR Baseline", "bpm", False),
    "max_hr": MetricSpec("max_hr", "Max HR", "bpm", False, None, None, False),
    "hr_recovery": MetricSpec("hr_recovery", "HR Recovery", "bpm", True, 12, 20),
    "body_battery": MetricSpec("body_battery", "Body Battery", "%", True, 45, 75),
    "stress": MetricSpec("stress", "Stress", "", False, 25, 50),
    "spo2": MetricSpec("spo2_avg", "SpO2", "%", True, 95, 97),
    "respiration": MetricSpec("respiration_avg", "Respiration", "brpm", False, 12, 17),
    "steps": MetricSpec("steps", "Steps", "", True, None, None, False),
    "active_calories": MetricSpec("active_calories", "Active Calories", "kcal", True, None, None, False),
    "active_minutes": MetricSpec("active_minutes", "Active Minutes", "min", True, 20, 60, False),
    "moderate_minutes": MetricSpec("moderate_intensity_min", "Moderate Minutes", "min", True, None, None, False),
    "vigorous_minutes": MetricSpec("vigorous_intensity_min", "Vigorous Minutes", "min", True, None, None, False),
    "distance": MetricSpec("distance_km", "Distance", "km", True, None, None, False),
    "floors": MetricSpec("floors_climbed", "Floors", "", True, None, None, False),
    "vo2max": MetricSpec("vo2max", "VO2 Max", "ml/kg/min", True),
    "cardio_load": MetricSpec("cardio_load", "Cardio Load", "", True),
    "load_balance": MetricSpec("load_balance", "Load Balance", "", True, 0.8, 1.3, True, True),
    "weight": MetricSpec("weight_kg", "Weight", "kg", False),
    "body_fat": MetricSpec("body_fat_pct", "Body Fat", "%", False),
    "muscle_mass": MetricSpec("muscle_mass_kg", "Muscle Mass", "kg", True),
    "bmi": MetricSpec("bmi", "BMI", "", False, 20, 25),
    "fitness_age": MetricSpec("fitness_age", "Fitness Age", "y", False),
    "biological_age": MetricSpec("biological_age", "Biological Age", "y", False),
}

RANGE_DAYS: dict[str, int | None] = {"7d": 7, "30d": 30, "90d": 90, "6m": 180, "1y": 365, "all": None}


def range_snaps(db: Session, end: date, range_key: str) -> list[HealthSnapshot]:
    days = RANGE_DAYS.get(range_key, 30)
    if days is None:
        return list(
            db.execute(
                select(HealthSnapshot).order_by(HealthSnapshot.date.asc())
            ).scalars().all()
        )
    start = end - timedelta(days=days - 1)
    return list(
        db.execute(
            select(HealthSnapshot)
            .where(HealthSnapshot.date >= start, HealthSnapshot.date <= end)
            .order_by(HealthSnapshot.date.asc())
        ).scalars().all()
    )


def _convert_value(spec: MetricSpec, value: float | int | None) -> float | None:
    if value is None:
        return None
    number = float(value)
    if spec.field in {"sleep_minutes", "sleep_deep_minutes", "sleep_rem_minutes", "sleep_light_minutes", "sleep_awake_minutes", "sleep_debt_minutes", "sleep_need_minutes"}:
        return round(number / 60.0, 2)
    return round(number, 2)


def _values(series: list[dict]) -> list[float]:
    return [point["value"] for point in series if point.get("value") is not None]


def _moving_average(series: list[dict], window: int = 7) -> list[dict]:
    output: list[dict] = []
    for index, point in enumerate(series):
        start = max(0, index - window + 1)
        sample = _values(series[start:index + 1])
        output.append({"date": point["date"], "value": round(mean(sample), 2) if sample else None})
    return output


def _linear_slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    x_mean = (len(values) - 1) / 2
    y_mean = mean(values)
    denom = sum((index - x_mean) ** 2 for index in range(len(values)))
    if denom == 0:
        return 0.0
    return sum((index - x_mean) * (value - y_mean) for index, value in enumerate(values)) / denom


def _trend_label(spec: MetricSpec, slope: float, avg_value: float | None) -> str:
    if avg_value in (None, 0) or abs(slope) < abs(avg_value) * 0.002:
        return "stable"
    improving = slope > 0 if spec.higher_is_better else slope < 0
    return "improving" if improving else "declining"


def _direction_context(spec: MetricSpec) -> str:
    if spec.target_range_is_best and spec.low is not None and spec.high is not None:
        return f"closer to the {spec.low:g}-{spec.high:g}{spec.unit} target range is better"
    return "higher is better" if spec.higher_is_better else "lower is better"


def _status_for(spec: MetricSpec, latest: float | None) -> str:
    if latest is None:
        return "no_data"
    if spec.low is None or spec.high is None:
        return "tracked"
    if spec.target_range_is_best:
        if spec.low <= latest <= spec.high:
            return "good"
        span = spec.high - spec.low
        near_low = spec.low - span * 0.35
        near_high = spec.high + span * 0.35
        if near_low <= latest <= near_high:
            return "watch"
        return "flag"
    if spec.higher_is_better:
        if latest >= spec.high:
            return "good"
        if latest >= spec.low:
            return "watch"
        return "flag"
    if latest <= spec.low:
        return "good"
    if latest <= spec.high:
        return "watch"
    return "flag"


def _period_comparison(values: list[float]) -> dict:
    if len(values) < 4:
        return {"delta": None, "delta_pct": None, "previous_avg": None}
    midpoint = len(values) // 2
    previous = values[:midpoint]
    current = values[midpoint:]
    previous_avg = mean(previous) if previous else None
    current_avg = mean(current) if current else None
    if previous_avg in (None, 0) or current_avg is None:
        return {"delta": None, "delta_pct": None, "previous_avg": previous_avg}
    delta = current_avg - previous_avg
    return {
        "delta": round(delta, 2),
        "delta_pct": round((delta / previous_avg) * 100, 1),
        "previous_avg": round(previous_avg, 2),
    }


def metric_explanation(metric: str, actual_age: float | None = None) -> str:
    age = f"{actual_age:.1f}" if actual_age is not None else "your profile age"
    notes = {
        "fitness_age": (
            f"Fitness Age estimates cardiovascular fitness versus your chronological age ({age}). "
            "VO2 max is the main driver. Resting HR, HRV, activity minutes, heart-rate recovery, and body composition adjust the estimate. "
            "Lower than your real age is better; equal or higher means cardiovascular markers are not yet outperforming age expectations."
        ),
        "biological_age": (
            f"Biological Age estimates recovery and autonomic stability versus your chronological age ({age}). "
            "Forge uses HRV baseline, resting HR baseline, sleep score/regularity, stress, body battery, SpO2/respiration, and body composition. "
            "This is a wearable-derived estimate, not a clinical biological-age blood test. Lower than actual age is better."
        ),
        "sleep_score": (
            "Sleep Score prioritises Garmin's reported sleep score when available. The supporting interpretation looks at sleep duration, sleep need/debt, deep sleep, REM sleep, awake time, and timing consistency. "
            "A strong sleep profile usually combines enough total sleep with stable timing and healthy deep/REM proportions."
        ),
        "sleep_hours": "Sleep Hours is total sleep time converted from Garmin sleep seconds. Most adults perform best around 7-9 hours, but the right target depends on recent strain and sleep debt.",
        "sleep_debt": "Sleep Debt is sleep need minus actual sleep when Garmin reports sleep need. If Garmin does not report sleep need, Forge estimates against an 8-hour baseline.",
        "hrv": "HRV is Garmin's nightly RMSSD-style recovery signal when available. Higher is generally better relative to your own baseline, but sudden spikes can also reflect noise.",
        "rhr": "Resting HR is interpreted against your recent baseline. Lower is generally better when it is not caused by illness, under-fuelling, or measurement artefacts.",
        "respiration": "Respiration is breathing rate. Stability inside your normal range matters more than simply being higher; sustained elevation can signal stress, heat, illness, or poor recovery.",
        "steps": "Steps measure daily movement volume. Higher is usually positive until it conflicts with recovery or strain targets; variability is expected and not automatically a problem.",
        "strain": "Strain combines passive movement and intensity minutes into a daily training-load estimate. More is not always better; the target depends on recovery.",
        "cardio_load": "Cardio Load estimates aerobic training load from active, moderate, and vigorous minutes. It is a transparent approximation until workout heart-rate samples are available.",
        "load_balance": "Load Balance compares recent acute load with longer-term chronic load. Around 0.8-1.3 is usually sustainable; high values can indicate overreaching.",
    }
    return notes.get(metric, "Forge interprets this metric against its direction, range history, and recent baseline. The chart shows raw history plus a 7-day moving average.")


def metric_flags(metric: str, spec: MetricSpec, series: list[dict], coverage: dict) -> list[dict]:
    values = _values(series)
    flags: list[dict] = []
    if coverage["coverage_pct"] < 65:
        flags.append({
            "date": None,
            "severity": "watch",
            "title": "Low data coverage",
            "detail": f"{coverage['covered_days']} of {coverage['expected_days']} days have {spec.label} data.",
            "metric": metric,
        })
    if len(values) < 7:
        return flags

    avg = mean(values)
    sd = pstdev(values) or 0.0
    latest_point = next((point for point in reversed(series) if point.get("value") is not None), None)
    latest = latest_point["value"] if latest_point else None
    if latest is not None and sd > 0:
        z = (latest - avg) / sd
        if abs(z) >= 1.8:
            if spec.target_range_is_best and spec.low is not None and spec.high is not None:
                bad_direction = latest < spec.low or latest > spec.high
            else:
                bad_direction = z < 0 if spec.higher_is_better else z > 0
            if bad_direction or spec.volatility_sensitive:
                flags.append({
                    "date": latest_point["date"],
                    "severity": "alert" if bad_direction and abs(z) >= 2.4 else ("watch" if bad_direction else "info"),
                    "title": f"{spec.label} {'worse' if bad_direction else 'better'} than usual",
                    "detail": f"Latest {latest:g}{spec.unit} is {abs(z):.1f} standard deviations {'below' if z < 0 else 'above'} this range average. For this metric, {_direction_context(spec)}.",
                    "metric": metric,
                })

    status = _status_for(spec, latest)
    if status == "flag":
        flags.append({
            "date": latest_point["date"] if latest_point else None,
            "severity": "alert",
            "title": f"{spec.label} outside target",
            "detail": f"Latest value is {latest:g}{spec.unit}; target range is {spec.low:g}-{spec.high:g}{spec.unit}.",
            "metric": metric,
        })
    return flags[:4]


def metric_insights(metric: str, spec: MetricSpec, series: list[dict], comparison: dict) -> list[dict]:
    values = _values(series)
    if len(values) < 7:
        return [{
            "title": "More history needed",
            "summary": f"Forge needs at least 7 days of {spec.label} to detect a reliable trend.",
            "confidence": "low",
            "metric": metric,
        }]

    slope = _linear_slope(values)
    avg_value = mean(values)
    trend = _trend_label(spec, slope, avg_value)
    latest = values[-1]
    delta_pct = comparison.get("delta_pct")
    direction = "higher" if delta_pct and delta_pct > 0 else "lower"
    context = _direction_context(spec)
    if spec.target_range_is_best and spec.low is not None and spec.high is not None:
        if latest < spec.low:
            if slope > 0:
                summary = f"{spec.label} is below target but moving toward range. Latest is {latest:g}{spec.unit}; target range is {spec.low:g}-{spec.high:g}{spec.unit}."
            else:
                summary = f"{spec.label} is below target. Latest is {latest:g}{spec.unit}; target range is {spec.low:g}-{spec.high:g}{spec.unit}. Trend direction matters less than closing the gap to target."
            title = f"{spec.label} is below target"
        elif latest > spec.high:
            if slope < 0:
                summary = f"{spec.label} is above target but easing back toward range. Latest is {latest:g}{spec.unit}; target range is {spec.low:g}-{spec.high:g}{spec.unit}."
            else:
                summary = f"{spec.label} is above target. Latest is {latest:g}{spec.unit}; target range is {spec.low:g}-{spec.high:g}{spec.unit}. Watch recovery before adding more load."
            title = f"{spec.label} is above target"
        else:
            summary = f"{spec.label} is within target. Latest is {latest:g}{spec.unit}; target range is {spec.low:g}-{spec.high:g}{spec.unit}. Keep it close to range rather than simply higher or lower."
            title = f"{spec.label} is within target"
        return [{
            "title": title,
            "summary": summary,
            "confidence": "medium" if len(values) < 21 else "high",
            "metric": metric,
        }]
    movement_note = "positive" if trend == "improving" else "cautionary"
    if trend == "stable":
        summary = f"{spec.label} is stable across this range. Latest is {latest:g}{spec.unit}, with an average of {avg_value:.1f}{spec.unit}. For this metric, {context}."
    else:
        summary = f"{spec.label} is {trend}. That is a {movement_note} direction because {context}. Latest is {latest:g}{spec.unit}, and this period is {abs(delta_pct or 0):.1f}% {direction} than the previous period."
    return [{
        "title": f"{spec.label} is {trend}",
        "summary": summary,
        "confidence": "medium" if len(values) < 21 else "high",
        "metric": metric,
    }]


def metric_payload(db: Session, metric: str, range_key: str, end: date | None = None) -> dict:
    spec = METRIC_SPECS.get(metric)
    if not spec:
        raise KeyError(metric)
    end = end or date.today()
    expected_days = RANGE_DAYS.get(range_key, 30)
    snaps = range_snaps(db, end, range_key)
    series = []
    for snap in snaps:
        value = _convert_value(spec, getattr(snap, spec.field, None))
        if value is not None:
            series.append({"date": snap.date.isoformat(), "value": value})
    values = _values(series)
    comparison = _period_comparison(values)
    avg_value = round(mean(values), 2) if values else None
    coverage = {
        "covered_days": len(series),
        "expected_days": expected_days or len(snaps),
        "coverage_pct": round((len(series) / (expected_days or len(snaps) or 1)) * 100, 1),
    }
    return {
        "metric": metric,
        "label": spec.label,
        "unit": spec.unit,
        "range": range_key,
        "series": series,
        "moving_avg_7d": _moving_average(series),
        "coverage": coverage,
        "comparison": comparison,
        "status": _status_for(spec, values[-1] if values else None),
        "explanation": metric_explanation(metric, actual_age_years(db)),
        "stats": {
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "avg": avg_value,
            "latest": values[-1] if values else None,
            "count": len(values),
            "std": round(pstdev(values), 2) if len(values) > 1 else None,
            "trend": _trend_label(spec, _linear_slope(values), avg_value) if values else "no_data",
        },
        "flags": metric_flags(metric, spec, series, coverage),
        "insights": metric_insights(metric, spec, series, comparison),
    }


def dashboard_insights(db: Session, range_key: str = "90d", end: date | None = None) -> dict:
    end = end or date.today()
    priority_metrics = ["recovery", "sleep_score", "hrv", "rhr", "stress", "strain", "body_battery", "fitness_age", "biological_age"]
    payloads = []
    for metric in priority_metrics:
        try:
            payloads.append(metric_payload(db, metric, range_key, end))
        except KeyError:
            continue

    flags = [flag for payload in payloads for flag in payload["flags"]]
    severity_rank = {"alert": 0, "watch": 1, "info": 2}
    flags.sort(key=lambda item: severity_rank.get(item.get("severity", "info"), 9))
    insights = [payload["insights"][0] for payload in payloads if payload["insights"]]
    insights.sort(key=lambda item: {"high": 0, "medium": 1, "low": 2}.get(item.get("confidence", "low"), 9))

    return {
        "range": range_key,
        "generated_at": end.isoformat(),
        "flags": flags[:8],
        "insights": insights[:8],
        "patterns": behavior_patterns(range_snaps(db, end, range_key)),
    }


def _parse_local_hour(value: str | None) -> float | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.hour + parsed.minute / 60


def _bucket_label(hour: float) -> str:
    bucket = int(hour * 2) / 2
    hour_part = int(bucket) % 24
    minute_part = 30 if bucket % 1 else 0
    return f"{hour_part:02d}:{minute_part:02d}"


def best_bedtime_pattern(snaps: list[HealthSnapshot]) -> dict:
    buckets: dict[str, list[float]] = {}
    for snap in snaps:
        if snap.sleep_score is None:
            continue
        hour = _parse_local_hour(snap.sleep_start_local)
        if hour is None:
            continue
        buckets.setdefault(_bucket_label(hour), []).append(float(snap.sleep_score))

    candidates = [(label, vals) for label, vals in buckets.items() if len(vals) >= 3]
    if not candidates:
        return {
            "id": "best_bedtime",
            "title": "Optimal sleep time needs more history",
            "summary": "Forge needs at least 3 nights in the same 30-minute bedtime window to identify your strongest sleep timing pattern.",
            "confidence": "low",
            "evidence": [f"{sum(len(v) for v in buckets.values())} nights with bedtime and sleep-score data"],
            "metric": "sleep_score",
        }

    best_label, best_values = max(candidates, key=lambda item: mean(item[1]))
    overall_values = [score for values in buckets.values() for score in values]
    lift = mean(best_values) - mean(overall_values)
    confidence = "high" if len(best_values) >= 8 and len(overall_values) >= 30 else "medium"
    return {
        "id": "best_bedtime",
        "title": f"Best sleep scores cluster around {best_label}",
        "summary": f"Nights starting around {best_label} average {mean(best_values):.0f} sleep score, {lift:+.0f} points versus your range average.",
        "confidence": confidence,
        "evidence": [f"{len(best_values)} nights in this window", f"{len(overall_values)} nights analysed"],
        "metric": "sleep_score",
    }


def training_recovery_pattern(snaps: list[HealthSnapshot]) -> dict:
    strain_values = [float(s.strain) for s in snaps if s.strain is not None]
    if len(strain_values) < 10:
        return {
            "id": "training_recovery_lag",
            "title": "Training recovery lag needs more workouts",
            "summary": "Forge needs at least 10 strain readings to compare hard days with next-day recovery.",
            "confidence": "low",
            "evidence": [f"{len(strain_values)} strain readings available"],
            "metric": "strain",
        }

    threshold = sorted(strain_values)[int(len(strain_values) * 0.75)]
    by_date = {snap.date: snap for snap in snaps}
    next_recoveries: list[float] = []
    all_recoveries = [float(s.recovery) for s in snaps if s.recovery is not None]
    for snap in snaps:
        if snap.strain is None or snap.strain < threshold:
            continue
        next_day = by_date.get(snap.date + timedelta(days=1))
        if next_day and next_day.recovery is not None:
            next_recoveries.append(float(next_day.recovery))

    if len(next_recoveries) < 3 or not all_recoveries:
        return {
            "id": "training_recovery_lag",
            "title": "Hard-day recovery pattern is still calibrating",
            "summary": f"Forge found {len(next_recoveries)} high-strain days with next-day recovery. More matched days will improve confidence.",
            "confidence": "low",
            "evidence": [f"High strain threshold: {threshold:.1f}", f"{len(next_recoveries)} matched next days"],
            "metric": "strain",
        }

    delta = mean(next_recoveries) - mean(all_recoveries)
    direction = "lower" if delta < 0 else "higher"
    return {
        "id": "training_recovery_lag",
        "title": f"High strain is followed by {direction} recovery",
        "summary": f"After top-quartile strain days, next-day recovery averages {mean(next_recoveries):.0f}, {delta:+.0f} versus your range average.",
        "confidence": "medium" if len(next_recoveries) < 8 else "high",
        "evidence": [f"High strain threshold: {threshold:.1f}", f"{len(next_recoveries)} matched next days"],
        "metric": "recovery",
    }


def stress_recovery_pattern(snaps: list[HealthSnapshot]) -> dict:
    pairs = [(float(s.stress), float(s.recovery)) for s in snaps if s.stress is not None and s.recovery is not None]
    if len(pairs) < 10:
        return {
            "id": "stress_recovery",
            "title": "Stress and recovery pattern needs more data",
            "summary": "Forge needs at least 10 days with both stress and recovery to estimate this relationship.",
            "confidence": "low",
            "evidence": [f"{len(pairs)} paired days available"],
            "metric": "stress",
        }

    xs, ys = zip(*pairs)
    x_avg, y_avg = mean(xs), mean(ys)
    numerator = sum((x - x_avg) * (y - y_avg) for x, y in pairs)
    denom = sqrt(sum((x - x_avg) ** 2 for x in xs) * sum((y - y_avg) ** 2 for y in ys))
    r = numerator / denom if denom else 0.0
    if abs(r) < 0.3:
        title = "Stress and recovery are not strongly linked yet"
        summary = f"Across {len(pairs)} paired days, stress and recovery correlation is r={r:.2f}."
        confidence = "medium"
    else:
        title = "Stress is linked with recovery movement"
        summary = f"Across {len(pairs)} paired days, stress and recovery correlation is r={r:.2f}."
        confidence = "high" if len(pairs) >= 30 else "medium"
    return {
        "id": "stress_recovery",
        "title": title,
        "summary": summary,
        "confidence": confidence,
        "evidence": [f"{len(pairs)} paired days", f"Pearson r={r:.2f}"],
        "metric": "stress",
    }


def sleep_duration_score_pattern(snaps: list[HealthSnapshot]) -> dict:
    pairs = [
        (float(s.sleep_minutes) / 60, float(s.sleep_score))
        for s in snaps
        if s.sleep_minutes is not None and s.sleep_score is not None
    ]
    if len(pairs) < 10:
        return {
            "id": "sleep_duration_score",
            "title": "Sleep duration pattern needs more nights",
            "summary": "Forge needs at least 10 nights with duration and sleep score to estimate your best duration window.",
            "confidence": "low",
            "evidence": [f"{len(pairs)} paired nights available"],
            "metric": "sleep_hours",
        }
    buckets = {
        "<6h": [score for hours, score in pairs if hours < 6],
        "6-7h": [score for hours, score in pairs if 6 <= hours < 7],
        "7-8h": [score for hours, score in pairs if 7 <= hours < 8],
        "8-9h": [score for hours, score in pairs if 8 <= hours < 9],
        "9h+": [score for hours, score in pairs if hours >= 9],
    }
    candidates = [(label, vals) for label, vals in buckets.items() if len(vals) >= 3]
    if not candidates:
        return {
            "id": "sleep_duration_score",
            "title": "Sleep duration pattern is calibrating",
            "summary": "Your nights are not yet distributed across enough duration windows to identify a clear best range.",
            "confidence": "low",
            "evidence": [f"{len(pairs)} paired nights available"],
            "metric": "sleep_hours",
        }
    best_label, best_values = max(candidates, key=lambda item: mean(item[1]))
    return {
        "id": "sleep_duration_score",
        "title": f"Best sleep scores follow {best_label} sleep",
        "summary": f"{best_label} nights average {mean(best_values):.0f} sleep score across {len(best_values)} nights.",
        "confidence": "high" if len(pairs) >= 30 else "medium",
        "evidence": [f"{len(best_values)} nights in best window", f"{len(pairs)} nights analysed"],
        "metric": "sleep_hours",
    }


def sleep_debt_recovery_pattern(snaps: list[HealthSnapshot]) -> dict:
    by_date = {snap.date: snap for snap in snaps}
    pairs: list[tuple[float, float]] = []
    for snap in snaps:
        if snap.sleep_debt_minutes is None:
            continue
        next_day = by_date.get(snap.date + timedelta(days=1))
        if next_day and next_day.recovery is not None:
            pairs.append((float(snap.sleep_debt_minutes) / 60, float(next_day.recovery)))
    if len(pairs) < 10:
        return {
            "id": "sleep_debt_recovery",
            "title": "Sleep debt recovery pattern needs more nights",
            "summary": "Forge needs at least 10 nights with sleep debt and next-day recovery to estimate this relationship.",
            "confidence": "low",
            "evidence": [f"{len(pairs)} paired nights available"],
            "metric": "sleep_debt",
        }
    low_debt = [rec for debt, rec in pairs if debt <= 1.5]
    high_debt = [rec for debt, rec in pairs if debt > 2.5]
    if len(low_debt) < 3 or len(high_debt) < 3:
        return {
            "id": "sleep_debt_recovery",
            "title": "Sleep debt threshold is still calibrating",
            "summary": "Forge needs more nights on both low-debt and high-debt days to compare next-day recovery.",
            "confidence": "low",
            "evidence": [f"{len(low_debt)} low-debt nights", f"{len(high_debt)} high-debt nights"],
            "metric": "sleep_debt",
        }
    delta = mean(high_debt) - mean(low_debt)
    return {
        "id": "sleep_debt_recovery",
        "title": "Sleep debt changes next-day recovery",
        "summary": f"Recovery after >2.5h sleep debt averages {mean(high_debt):.0f}, {delta:+.0f} versus low-debt nights.",
        "confidence": "high" if len(pairs) >= 30 else "medium",
        "evidence": [f"{len(low_debt)} low-debt nights", f"{len(high_debt)} high-debt nights"],
        "metric": "sleep_debt",
    }


def sleep_stage_score_pattern(snaps: list[HealthSnapshot]) -> dict:
    pairs = []
    for snap in snaps:
        stage_total = (snap.sleep_deep_minutes or 0) + (snap.sleep_rem_minutes or 0) + (snap.sleep_light_minutes or 0)
        if stage_total <= 0 or snap.sleep_score is None:
            continue
        restorative_pct = ((snap.sleep_deep_minutes or 0) + (snap.sleep_rem_minutes or 0)) / stage_total * 100
        pairs.append((restorative_pct, float(snap.sleep_score)))
    if len(pairs) < 10:
        return {
            "id": "sleep_stage_score",
            "title": "Sleep stage pattern needs more complete stage data",
            "summary": "Forge needs at least 10 nights with deep, REM, light, and score data to estimate stage impact.",
            "confidence": "low",
            "evidence": [f"{len(pairs)} complete stage nights available"],
            "metric": "sleep_score",
        }
    high_stage = [score for pct, score in pairs if pct >= 38]
    low_stage = [score for pct, score in pairs if pct < 30]
    if len(high_stage) < 3 or len(low_stage) < 3:
        avg_pct = mean([pct for pct, _ in pairs])
        return {
            "id": "sleep_stage_score",
            "title": "Restorative sleep share is being tracked",
            "summary": f"Deep + REM sleep averages {avg_pct:.0f}% of staged sleep across {len(pairs)} nights.",
            "confidence": "medium",
            "evidence": [f"{len(pairs)} complete stage nights"],
            "metric": "sleep_score",
        }
    delta = mean(high_stage) - mean(low_stage)
    return {
        "id": "sleep_stage_score",
        "title": "Deep + REM share is linked with sleep score",
        "summary": f"Nights with >=38% deep + REM average {mean(high_stage):.0f} sleep score, {delta:+.0f} versus <30% nights.",
        "confidence": "high" if len(pairs) >= 30 else "medium",
        "evidence": [f"{len(high_stage)} high restorative nights", f"{len(low_stage)} low restorative nights"],
        "metric": "sleep_score",
    }


def bedtime_consistency_pattern(snaps: list[HealthSnapshot]) -> dict:
    hours = [_parse_local_hour(s.sleep_start_local) for s in snaps if s.sleep_start_local]
    scores = [float(s.sleep_score) for s in snaps if s.sleep_score is not None]
    hours = [h for h in hours if h is not None]
    if len(hours) < 10 or not scores:
        return {
            "id": "bedtime_consistency",
            "title": "Bedtime consistency needs more nights",
            "summary": "Forge needs at least 10 nights with bedtime data to estimate regularity.",
            "confidence": "low",
            "evidence": [f"{len(hours)} bedtime readings available"],
            "metric": "sleep_score",
        }
    # Convert post-midnight bedtimes into a continuous evening window.
    adjusted = [h + 24 if h < 12 else h for h in hours]
    variance_minutes = pstdev(adjusted) * 60 if len(adjusted) > 1 else 0
    confidence = "high" if len(hours) >= 30 else "medium"
    return {
        "id": "bedtime_consistency",
        "title": "Bedtime consistency is measurable",
        "summary": f"Your bedtime varies by about +/-{variance_minutes:.0f} minutes across this range. Lower variance usually supports steadier sleep quality.",
        "confidence": confidence,
        "evidence": [f"{len(hours)} bedtime readings", f"{len(scores)} sleep-score nights"],
        "metric": "sleep_score",
    }


def behavior_patterns(snaps: list[HealthSnapshot]) -> list[dict]:
    """Deterministic pattern cards. AI may narrate these, but does not invent them."""
    return [
        best_bedtime_pattern(snaps),
        sleep_duration_score_pattern(snaps),
        sleep_debt_recovery_pattern(snaps),
        sleep_stage_score_pattern(snaps),
        bedtime_consistency_pattern(snaps),
        training_recovery_pattern(snaps),
        stress_recovery_pattern(snaps),
    ]


def correlations(db: Session, metric: str, range_key: str = "90d", end: date | None = None) -> list[dict]:
    """Lightweight Pearson correlations against other tracked metrics."""
    base = metric_payload(db, metric, range_key, end)["series"]
    by_date = {point["date"]: point["value"] for point in base}
    if len(by_date) < 10:
        return []
    output = []
    for other in ("sleep_score", "hrv", "rhr", "stress", "strain", "body_battery", "recovery"):
        if other == metric:
            continue
        other_series = metric_payload(db, other, range_key, end)["series"]
        pairs = [(by_date[p["date"]], p["value"]) for p in other_series if p["date"] in by_date]
        if len(pairs) < 10:
            continue
        xs, ys = zip(*pairs)
        x_avg, y_avg = mean(xs), mean(ys)
        numerator = sum((x - x_avg) * (y - y_avg) for x, y in pairs)
        denom = sqrt(sum((x - x_avg) ** 2 for x in xs) * sum((y - y_avg) ** 2 for y in ys))
        if denom:
            r = round(numerator / denom, 2)
            if abs(r) >= 0.35:
                output.append({"metric": other, "r": r})
    return sorted(output, key=lambda item: abs(item["r"]), reverse=True)[:5]
