"""Derived special metrics for Forge.

These metrics sit above the raw Garmin daily fields. They are intentionally
transparent and conservative: if Forge does not persist the required input
data yet, the metric returns a data-limited payload rather than inventing a
number.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import sqrt
from statistics import mean, pstdev
from typing import Any

from sqlalchemy.orm import Session

from app.models.health import HealthSnapshot
from app.services.insights import range_snaps


@dataclass(frozen=True)
class SpecialMetric:
    key: str
    label: str
    value: float | str | None
    unit: str = ""
    score: float | None = None
    status: str = "info"
    tone: str = "neutral"
    summary: str = ""
    data_quality: str = "limited"
    inputs: tuple[str, ...] = ()
    details: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "unit": self.unit,
            "score": self.score,
            "status": self.status,
            "tone": self.tone,
            "summary": self.summary,
            "data_quality": self.data_quality,
            "inputs": list(self.inputs),
            "details": list(self.details),
        }


def special_metrics_payload(db: Session, end: date, range_key: str = "90d") -> dict[str, Any]:
    snaps = range_snaps(db, end, range_key)
    return {
        "range": range_key,
        "generated_at": end.isoformat(),
        "metrics": special_metrics_from_snaps(snaps, end),
    }


def special_metrics_from_snaps(snaps: list[HealthSnapshot], end: date | None = None) -> dict[str, dict[str, Any]]:
    end = end or date.today()
    ordered = sorted(snaps, key=lambda snap: snap.date)
    metrics = [
        sleep_regularity_index(ordered),
        social_jetlag(ordered),
        recovery_half_life(ordered),
        hrv_guided_training_gate(ordered),
        physiological_anomaly_load(ordered),
        sleep_architecture_confidence(ordered),
        respiratory_stability_sleep(ordered),
        training_monotony(ordered),
        resilience_ratio(ordered),
    ]
    return {metric.key: metric.as_dict() for metric in metrics}


def sleep_regularity_index(snaps: list[HealthSnapshot]) -> SpecialMetric:
    starts = _dated_hours(snaps, "sleep_start_local")
    ends = _dated_hours(snaps, "sleep_end_local")
    if len(starts) < 5:
        return _limited(
            "sleep_regularity",
            "Sleep Regularity",
            "Need at least 5 nights with sleep start times to score schedule regularity.",
            ("sleep_start_local", "sleep_end_local"),
        )

    start_shifts = _adjacent_shifts_minutes(starts)
    end_shifts = _adjacent_shifts_minutes(ends)
    shifts = start_shifts + end_shifts
    if not shifts:
        return _limited(
            "sleep_regularity",
            "Sleep Regularity",
            "Need consecutive nights with sleep timing to score regularity.",
            ("sleep_start_local", "sleep_end_local"),
        )

    avg_shift = mean(shifts)
    score = _clamp(100 - (avg_shift / 90) * 100, 0, 100)
    status, tone = _score_status(score, good=75, watch=55)
    return SpecialMetric(
        key="sleep_regularity",
        label="Sleep Regularity",
        value=round(score, 0),
        unit="%",
        score=round(score, 0),
        status=status,
        tone=tone,
        summary=f"Average sleep schedule shift is {avg_shift:.0f} minutes night-to-night.",
        data_quality=_quality(len(starts)),
        inputs=("sleep_start_local", "sleep_end_local"),
        details=(
            "Scores bedtime and wake-time stability across consecutive nights.",
            "Higher is better. Large bedtime or wake shifts reduce the score.",
        ),
    )


def social_jetlag(snaps: list[HealthSnapshot]) -> SpecialMetric:
    mids = []
    for snap in snaps:
        start = _local_hour(snap.sleep_start_local)
        end_hour = _local_hour(snap.sleep_end_local)
        if start is None or end_hour is None:
            continue
        mids.append((snap.date.weekday(), _sleep_midpoint(start, end_hour)))

    weekday = [mid for day, mid in mids if day < 5]
    weekend = [mid for day, mid in mids if day >= 5]
    if len(weekday) < 5 or len(weekend) < 2:
        return _limited(
            "social_jetlag",
            "Social Jetlag",
            "Need weekday and weekend sleep timing to compare midsleep drift.",
            ("sleep_start_local", "sleep_end_local"),
        )

    weekday_mid = _circular_mean(weekday)
    weekend_mid = _circular_mean(weekend)
    drift = _circular_hour_diff(weekday_mid, weekend_mid)
    score = _clamp(100 - (drift / 2.5) * 100, 0, 100)
    status, tone = _score_status(score, good=80, watch=55)
    return SpecialMetric(
        key="social_jetlag",
        label="Social Jetlag",
        value=round(drift, 1),
        unit="h",
        score=round(score, 0),
        status=status,
        tone=tone,
        summary=f"Weekend midsleep differs from weekday midsleep by {drift:.1f} hours.",
        data_quality=_quality(len(mids)),
        inputs=("sleep_start_local", "sleep_end_local"),
        details=(
            "Compares weekday and weekend midsleep timing.",
            "Lower drift usually supports circadian stability.",
        ),
    )


def recovery_half_life(snaps: list[HealthSnapshot]) -> SpecialMetric:
    pairs = [(snap.date, snap.strain, snap.recovery) for snap in snaps if snap.strain is not None and snap.recovery is not None]
    if len(pairs) < 14:
        return _limited(
            "recovery_half_life",
            "Recovery Half-Life",
            "Need at least 14 days with strain and recovery to estimate recovery lag.",
            ("strain", "recovery"),
        )

    strain_values = [float(strain) for _, strain, _ in pairs if strain is not None]
    threshold = _percentile(strain_values, 75)
    baseline = mean(float(rec) for _, _, rec in pairs if rec is not None)
    by_date = {snap.date: snap for snap in snaps}
    lags: list[int] = []
    for day, strain, recovery in pairs:
        if strain is None or recovery is None or strain < threshold:
            continue
        recovered_day = None
        for lag in range(1, 5):
            next_snap = by_date.get(day + timedelta(days=lag))
            if next_snap and next_snap.recovery is not None and next_snap.recovery >= baseline:
                recovered_day = lag
                break
        if recovered_day is not None:
            lags.append(recovered_day)

    if not lags:
        return _limited(
            "recovery_half_life",
            "Recovery Half-Life",
            "High-strain days were found, but there was not enough next-day recovery data.",
            ("strain", "recovery"),
        )

    lag = mean(lags)
    score = _clamp(100 - ((lag - 1) / 3) * 100, 0, 100)
    status, tone = _score_status(score, good=70, watch=45)
    return SpecialMetric(
        key="recovery_half_life",
        label="Recovery Half-Life",
        value=round(lag, 1),
        unit="d",
        score=round(score, 0),
        status=status,
        tone=tone,
        summary=f"After top-quartile strain days, recovery returns to baseline in about {lag:.1f} days.",
        data_quality=_quality(len(lags) * 7),
        inputs=("strain", "recovery"),
        details=(
            f"High strain threshold in this range is {threshold:.0f}.",
            f"Baseline recovery across the range is {baseline:.0f}.",
        ),
    )


def hrv_guided_training_gate(snaps: list[HealthSnapshot]) -> SpecialMetric:
    latest = _latest(snaps)
    if not latest:
        return _limited(
            "training_gate",
            "Training Gate",
            "No current day available for training guidance.",
            ("recovery", "readiness", "hrv_ms", "rhr_bpm", "sleep_debt_minutes", "strain"),
        )

    score = 55.0
    details: list[str] = []
    if latest.recovery is not None:
        score += (float(latest.recovery) - 55) * 0.25
        details.append(f"Recovery {latest.recovery:.0f}/100.")
    if latest.readiness is not None:
        score += (float(latest.readiness) - 55) * 0.18
        details.append(f"Readiness {latest.readiness:.0f}/100.")
    if latest.hrv_ms is not None and latest.hrv_baseline_ms:
        ratio = latest.hrv_ms / latest.hrv_baseline_ms
        score += (ratio - 1) * 25
        details.append(f"HRV is {ratio * 100:.0f}% of baseline.")
    if latest.rhr_bpm is not None and latest.rhr_baseline_bpm:
        score -= max(0, latest.rhr_bpm - latest.rhr_baseline_bpm) * 4
        details.append(f"RHR is {latest.rhr_bpm - latest.rhr_baseline_bpm:+.0f} bpm vs baseline.")
    if latest.sleep_debt_minutes is not None:
        score -= min(15, (latest.sleep_debt_minutes / 60) * 4)
        details.append(f"Sleep debt is {latest.sleep_debt_minutes / 60:.1f}h.")
    if latest.stress is not None:
        score -= max(0, latest.stress - 35) * 0.25
        details.append(f"Stress is {latest.stress:.0f}/100.")

    score = _clamp(score, 0, 100)
    if score >= 75:
        gate = "Intensity available"
    elif score >= 58:
        gate = "Moderate available"
    elif score >= 40:
        gate = "Easy aerobic"
    else:
        gate = "Rest only"
    status, tone = _score_status(score, good=70, watch=45)
    return SpecialMetric(
        key="training_gate",
        label="Training Gate",
        value=gate,
        unit="",
        score=round(score, 0),
        status=status,
        tone=tone,
        summary=f"{gate}. Score is {score:.0f}/100 from recovery, sleep, HRV, RHR, and stress.",
        data_quality=_quality(len(details) * 12),
        inputs=("recovery", "readiness", "hrv_ms", "rhr_bpm", "sleep_debt_minutes", "stress"),
        details=tuple(details),
    )


def physiological_anomaly_load(snaps: list[HealthSnapshot]) -> SpecialMetric:
    latest = _latest(snaps)
    if not latest or len(snaps) < 14:
        return _limited(
            "physiological_anomaly_load",
            "Physiological Stability",
            "Need at least 14 days of history to detect unusual physiology.",
            ("hrv_ms", "rhr_bpm", "stress", "respiration_avg", "spo2_avg", "body_battery"),
        )

    specs = (
        ("hrv_ms", "HRV", False, 5.0),
        ("rhr_bpm", "RHR", True, 3.0),
        ("stress", "stress", True, 8.0),
        ("respiration_avg", "respiration", True, 1.0),
        ("spo2_avg", "SpO2", False, 1.0),
        ("body_battery", "body battery", False, 10.0),
    )
    drivers: list[tuple[str, float]] = []
    for field, label, high_is_bad, min_sd in specs:
        current = getattr(latest, field, None)
        vals = [float(getattr(snap, field)) for snap in snaps[:-1] if getattr(snap, field, None) is not None]
        if current is None or len(vals) < 7:
            continue
        sd = max(pstdev(vals), min_sd)
        if sd <= 0:
            continue
        z = (float(current) - mean(vals)) / sd
        bad_z = z if high_is_bad else -z
        if bad_z > 0:
            drivers.append((label, bad_z))

    anomaly = sum(min(3.0, z) for _, z in drivers)
    stability = _clamp(100 - (anomaly / 12) * 100, 0, 100)
    status, tone = _score_status(stability, good=75, watch=55)
    top = sorted(drivers, key=lambda item: item[1], reverse=True)[:3]
    driver_text = ", ".join(f"{label} {z:.1f}z" for label, z in top) or "no major outliers"
    return SpecialMetric(
        key="physiological_anomaly_load",
        label="Physiological Stability",
        value=round(stability, 0),
        unit="%",
        score=round(stability, 0),
        status=status,
        tone=tone,
        summary=f"Stability is {stability:.0f}/100; top signals: {driver_text}.",
        data_quality=_quality(len(snaps)),
        inputs=tuple(field for field, _, _, _ in specs),
        details=tuple(f"{label}: {z:.1f} standard deviations from baseline" for label, z in top),
    )


def sleep_architecture_confidence(snaps: list[HealthSnapshot]) -> SpecialMetric:
    latest = _latest(snaps)
    if not latest or latest.sleep_minutes is None:
        return _limited(
            "sleep_architecture_confidence",
            "Sleep Architecture Confidence",
            "No sleep duration is available for the selected day.",
            ("sleep_minutes", "sleep_deep_minutes", "sleep_rem_minutes", "sleep_light_minutes", "sleep_awake_minutes"),
        )

    fields = (latest.sleep_deep_minutes, latest.sleep_rem_minutes, latest.sleep_light_minutes, latest.sleep_awake_minutes)
    present = [value for value in fields if value is not None]
    coverage = len(present) / len(fields)
    stage_total = sum(int(value) for value in present)
    expected = max(1, latest.sleep_minutes + int(latest.sleep_awake_minutes or 0))
    ratio = stage_total / expected if stage_total else 0
    fit_score = _clamp(100 - abs(ratio - 1) * 100, 0, 100) if coverage == 1 else coverage * 75
    score = _clamp((coverage * 65) + (fit_score * 0.35), 0, 100)
    status, tone = _score_status(score, good=80, watch=55)
    return SpecialMetric(
        key="sleep_architecture_confidence",
        label="Sleep Architecture Confidence",
        value=round(score, 0),
        unit="%",
        score=round(score, 0),
        status=status,
        tone=tone,
        summary=f"{len(present)} of 4 sleep-stage fields are present; stage coverage is {ratio * 100:.0f}% of reported sleep window.",
        data_quality="high" if coverage == 1 else ("medium" if coverage >= 0.5 else "low"),
        inputs=("sleep_minutes", "sleep_deep_minutes", "sleep_rem_minutes", "sleep_light_minutes", "sleep_awake_minutes"),
        details=(
            "High confidence means duration, awake time, light, deep, and REM are internally consistent.",
            "Low confidence means sleep-stage insights should be treated as partial.",
        ),
    )


def respiratory_stability_sleep(snaps: list[HealthSnapshot]) -> SpecialMetric:
    latest = _latest(snaps)
    if not latest or latest.respiration_avg is None:
        return _limited(
            "respiratory_stability_sleep",
            "Respiratory Stability",
            "Need respiration data to assess breathing stability.",
            ("respiration_avg", "respiration_sleep", "spo2_avg"),
        )

    baseline_vals = [float(snap.respiration_avg) for snap in snaps[:-1] if snap.respiration_avg is not None]
    baseline = mean(baseline_vals) if baseline_vals else latest.respiration_avg
    drift = abs(float(latest.respiration_avg) - baseline)
    score = _clamp(100 - (drift / 4) * 70, 0, 100)
    if latest.spo2_avg is not None and latest.spo2_avg < 95:
        score -= (95 - latest.spo2_avg) * 8
    score = _clamp(score, 0, 100)
    status, tone = _score_status(score, good=78, watch=55)
    return SpecialMetric(
        key="respiratory_stability_sleep",
        label="Respiratory Stability",
        value=round(score, 0),
        unit="%",
        score=round(score, 0),
        status=status,
        tone=tone,
        summary=f"Respiration is {latest.respiration_avg:.1f} brpm, {drift:.1f} brpm from recent baseline.",
        data_quality=_quality(len(baseline_vals) + 1),
        inputs=("respiration_avg", "respiration_sleep", "spo2_avg"),
        details=(
            f"Recent baseline is {baseline:.1f} brpm.",
            f"SpO2 is {latest.spo2_avg:.1f}%." if latest.spo2_avg is not None else "SpO2 is not available for this day.",
        ),
    )


def training_monotony(snaps: list[HealthSnapshot]) -> SpecialMetric:
    loads = [float(snap.cardio_load) for snap in snaps[-7:] if snap.cardio_load is not None]
    if len(loads) < 5:
        return _limited(
            "training_monotony",
            "Training Monotony",
            "Need at least 5 recent days of cardio load to score monotony.",
            ("cardio_load",),
        )
    avg = mean(loads)
    sd = pstdev(loads)
    monotony = avg / sd if sd > 0 else 3.0
    strain = monotony * sum(loads)
    score = _clamp(100 - ((monotony - 1) / 1.5) * 100, 0, 100)
    status, tone = _score_status(score, good=70, watch=45)
    return SpecialMetric(
        key="training_monotony",
        label="Training Monotony",
        value=round(monotony, 2),
        unit="",
        score=round(score, 0),
        status=status,
        tone=tone,
        summary=f"7-day monotony is {monotony:.2f}; monotony-adjusted strain is {strain:.0f}.",
        data_quality=_quality(len(loads) * 12),
        inputs=("cardio_load",),
        details=(
            "Monotony = 7-day average load divided by load standard deviation.",
            "High monotony means similar load every day with less variation.",
        ),
    )


def resilience_ratio(snaps: list[HealthSnapshot]) -> SpecialMetric:
    pairs: list[tuple[float, float]] = []
    for index, snap in enumerate(snaps[:-1]):
        next_snap = snaps[index + 1]
        if snap.strain is None or next_snap.recovery is None:
            continue
        pairs.append((float(snap.strain), float(next_snap.recovery)))
    if len(pairs) < 12:
        return _limited(
            "resilience_ratio",
            "Resilience Ratio",
            "Need at least 12 strain-to-next-day-recovery pairs to score resilience.",
            ("strain", "next_day_recovery"),
        )
    r = _correlation([x for x, _ in pairs], [y for _, y in pairs])
    score = _clamp(65 + (r * 35), 0, 100)
    status, tone = _score_status(score, good=70, watch=50)
    return SpecialMetric(
        key="resilience_ratio",
        label="Resilience Ratio",
        value=round(score, 0),
        unit="%",
        score=round(score, 0),
        status=status,
        tone=tone,
        summary=f"Correlation r={r:.2f} between strain and next-day recovery. r ranges from -1 to +1; higher means recovery is holding better after strain.",
        data_quality=_quality(len(pairs) * 6),
        inputs=("strain", "recovery"),
        details=(
            "Positive or near-flat correlation means recovery is holding despite training load.",
            "Strong negative correlation means hard days are costing next-day recovery.",
        ),
    )


def _limited(key: str, label: str, summary: str, inputs: tuple[str, ...], label_value: str | None = None) -> SpecialMetric:
    return SpecialMetric(
        key=key,
        label=label,
        value=label_value,
        score=None,
        status="no_data",
        tone="neutral",
        summary=summary,
        data_quality="limited",
        inputs=inputs,
        details=("Forge will calculate this automatically once the required inputs are persisted.",),
    )


def _latest(snaps: list[HealthSnapshot]) -> HealthSnapshot | None:
    return snaps[-1] if snaps else None


def _local_hour(value: str | None) -> float | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.hour + parsed.minute / 60


def _dated_hours(snaps: list[HealthSnapshot], field: str) -> list[tuple[date, float]]:
    output: list[tuple[date, float]] = []
    for snap in snaps:
        hour = _local_hour(getattr(snap, field, None))
        if hour is not None:
            output.append((snap.date, hour))
    return output


def _adjacent_shifts_minutes(values: list[tuple[date, float]]) -> list[float]:
    shifts: list[float] = []
    for (_, prev), (_, cur) in zip(values, values[1:]):
        shifts.append(_circular_hour_diff(prev, cur) * 60)
    return shifts


def _sleep_midpoint(start: float, end_hour: float) -> float:
    duration = (end_hour - start) % 24
    return (start + duration / 2) % 24


def _circular_hour_diff(a: float, b: float) -> float:
    raw = abs(a - b) % 24
    return min(raw, 24 - raw)


def _circular_mean(hours: list[float]) -> float:
    if not hours:
        return 0.0
    # Sleep times cluster around night, so unwrapping around noon avoids the
    # midnight discontinuity without needing trig dependencies.
    shifted = [hour + 24 if hour < 12 else hour for hour in hours]
    return mean(shifted) % 24


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * (pct / 100)
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    weight = index - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _correlation(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 3:
        return 0.0
    x_mean = mean(xs)
    y_mean = mean(ys)
    x_var = sum((x - x_mean) ** 2 for x in xs)
    y_var = sum((y - y_mean) ** 2 for y in ys)
    if x_var == 0 or y_var == 0:
        return 0.0
    cov = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    return _clamp(cov / sqrt(x_var * y_var), -1, 1)


def _score_status(score: float, good: float, watch: float) -> tuple[str, str]:
    if score >= good:
        return "good", "good"
    if score >= watch:
        return "watch", "warn"
    return "alert", "bad"


def _quality(samples: int) -> str:
    if samples >= 60:
        return "high"
    if samples >= 21:
        return "medium"
    return "low"


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))
