"""Deterministic scoring engine — Fitness Age and Biological Age.

No AI involved here. Scores are computed from measured metrics.
The AI coach only interprets these values — it does not compute them.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.health import HealthSnapshot


# ────────────────────────────────────────────────
# FITNESS AGE
# ────────────────────────────────────────────────

def compute_fitness_age(snap: "HealthSnapshot | None", actual_age: float | None) -> tuple[float | None, str | None]:
    """
    Fitness Age = actual_age adjusted by cardiovascular/training metrics.
    Each driver contributes ± years relative to population norms.
    Returns (fitness_age, status_label).
    """
    drivers = fitness_age_drivers(snap, actual_age)
    if drivers is None:
        return None, None

    adjustments = [d["adjustment_years"] for d in drivers if d["adjustment_years"] is not None]
    if not adjustments:
        return None, None

    fitness_age = round(actual_age + sum(adjustments), 1)
    fitness_age = max(18.0, min(80.0, fitness_age))

    delta = fitness_age - actual_age
    if delta <= -5:
        status = "Excellent"
    elif delta <= -1:
        status = "Good"
    elif delta <= 2:
        status = "Fair"
    else:
        status = "Needs Work"

    return fitness_age, status


def fitness_age_drivers(snap: "HealthSnapshot | None", actual_age: float | None) -> list[dict] | None:
    """
    Returns list of driver dicts with:
      name, value, unit, adjustment_years, direction (helping/hurting/neutral)
    """
    if snap is None or actual_age is None:
        return None
    drivers = []

    # VO2max — biggest single driver (±6 years)
    if snap.vo2max is not None:
        # Population average VO2max declines ~1/decade after 25
        # Elite: >55, Good: 48-55, Average: 40-48, Below: <40
        baseline = max(20, 50 - (actual_age - 25) * 0.8)
        diff = snap.vo2max - baseline
        adj = round(-diff * 0.3, 1)  # each ml/kg/min worth ~0.3 years
        adj = max(-4.0, min(4.0, adj))
        drivers.append({
            "name": "VO2 Max",
            "value": snap.vo2max,
            "unit": "ml/kg/min",
            "adjustment_years": adj,
            "direction": "helping" if adj < -0.5 else ("hurting" if adj > 0.5 else "neutral"),
        })

    # Resting HR (±4 years)
    if snap.rhr_bpm is not None:
        # Elite: <50, Good: 50-60, Average: 60-70, High: >70
        rhr_adj = 0.0
        if snap.rhr_bpm < 50:
            rhr_adj = -2.5
        elif snap.rhr_bpm < 60:
            rhr_adj = -1.0
        elif snap.rhr_bpm < 70:
            rhr_adj = 0.5
        else:
            rhr_adj = 2.0
        drivers.append({
            "name": "Resting HR",
            "value": snap.rhr_bpm,
            "unit": "bpm",
            "adjustment_years": rhr_adj,
            "direction": "helping" if rhr_adj < -0.3 else ("hurting" if rhr_adj > 0.3 else "neutral"),
        })

    # HRV (±3 years)
    if snap.hrv_ms is not None:
        # HRV norms are highly individual but population baseline ~50-60ms at 30, declines ~1ms/year
        hrv_baseline = max(25, 65 - (actual_age - 25) * 1.0)
        hrv_diff = snap.hrv_ms - hrv_baseline
        hrv_adj = round(-hrv_diff * 0.06, 1)
        hrv_adj = max(-2.5, min(2.5, hrv_adj))
        drivers.append({
            "name": "HRV",
            "value": snap.hrv_ms,
            "unit": "ms",
            "adjustment_years": hrv_adj,
            "direction": "helping" if hrv_adj < -0.3 else ("hurting" if hrv_adj > 0.3 else "neutral"),
        })

    # Activity / active minutes (±2 years)
    if snap.active_minutes is not None or snap.vigorous_intensity_min is not None:
        active = (snap.active_minutes or 0) + (snap.vigorous_intensity_min or 0) * 2
        # WHO guidelines: 150 min moderate or 75 min vigorous/week → ~21 min/day
        daily_target = 21
        ratio = active / daily_target if daily_target else 1
        act_adj = round((1 - ratio) * 1.5, 1)
        act_adj = max(-2.0, min(2.0, act_adj))
        drivers.append({
            "name": "Activity",
            "value": active,
            "unit": "min",
            "adjustment_years": act_adj,
            "direction": "helping" if act_adj < -0.3 else ("hurting" if act_adj > 0.3 else "neutral"),
        })

    # Heart rate recovery proxy (±2 years)
    if snap.hr_recovery is not None:
        # Good HRR: >12bpm drop in 1min post-exercise
        hrr_adj = 0.0
        if snap.hr_recovery >= 20:
            hrr_adj = -1.5
        elif snap.hr_recovery >= 12:
            hrr_adj = -0.5
        elif snap.hr_recovery >= 6:
            hrr_adj = 0.5
        else:
            hrr_adj = 1.5
        drivers.append({
            "name": "HR Recovery",
            "value": snap.hr_recovery,
            "unit": "bpm",
            "adjustment_years": hrr_adj,
            "direction": "helping" if hrr_adj < -0.3 else ("hurting" if hrr_adj > 0.3 else "neutral"),
        })

    # Body composition (±2 years)
    if snap.body_fat_pct is not None:
        # Simplified: optimal BF% by age, gender-agnostic midpoint
        optimal_bf = 18 + (actual_age - 25) * 0.15
        bf_adj = round((snap.body_fat_pct - optimal_bf) * 0.08, 1)
        bf_adj = max(-1.5, min(1.5, bf_adj))
        drivers.append({
            "name": "Body Composition",
            "value": snap.body_fat_pct,
            "unit": "%",
            "adjustment_years": bf_adj,
            "direction": "helping" if bf_adj < -0.3 else ("hurting" if bf_adj > 0.3 else "neutral"),
        })

    return drivers if drivers else None


# ────────────────────────────────────────────────
# BIOLOGICAL AGE
# ────────────────────────────────────────────────

def compute_biological_age(snap: "HealthSnapshot | None", actual_age: float | None) -> tuple[float | None, str | None]:
    """
    Biological Age = actual_age adjusted by recovery, sleep, stress, autonomic balance.
    Separate from Fitness Age — answers: how well is the body maintaining homeostasis?
    """
    drivers = biological_age_drivers(snap, actual_age)
    if drivers is None:
        return None, None

    adjustments = [d["adjustment_years"] for d in drivers if d["adjustment_years"] is not None]
    if not adjustments:
        return None, None

    biological_age = round(actual_age + sum(adjustments), 1)
    biological_age = max(18.0, min(85.0, biological_age))

    delta = biological_age - actual_age
    if delta <= -4:
        status = "Optimal"
    elif delta <= 0:
        status = "Stable"
    elif delta <= 3:
        status = "Watch"
    else:
        status = "Elevated Risk"

    return biological_age, status


def biological_age_drivers(snap: "HealthSnapshot | None", actual_age: float | None) -> list[dict] | None:
    if snap is None or actual_age is None:
        return None
    drivers = []

    # HRV Baseline (±3 years)
    if snap.hrv_baseline_ms is not None:
        hrv_baseline_norm = max(30, 60 - (actual_age - 25) * 0.9)
        diff = snap.hrv_baseline_ms - hrv_baseline_norm
        adj = round(-diff * 0.07, 1)
        adj = max(-2.5, min(2.5, adj))
        drivers.append({
            "name": "HRV Baseline",
            "value": snap.hrv_baseline_ms,
            "unit": "ms",
            "adjustment_years": adj,
            "direction": "helping" if adj < -0.3 else ("hurting" if adj > 0.3 else "neutral"),
        })
    elif snap.hrv_ms is not None:
        hrv_baseline_norm = max(30, 60 - (actual_age - 25) * 0.9)
        diff = snap.hrv_ms - hrv_baseline_norm
        adj = round(-diff * 0.07, 1)
        adj = max(-2.5, min(2.5, adj))
        drivers.append({
            "name": "HRV Baseline",
            "value": snap.hrv_ms,
            "unit": "ms",
            "adjustment_years": adj,
            "direction": "helping" if adj < -0.3 else ("hurting" if adj > 0.3 else "neutral"),
        })

    # RHR Baseline (±2.5 years)
    if snap.rhr_baseline_bpm is not None or snap.rhr_bpm is not None:
        rhr = snap.rhr_baseline_bpm or snap.rhr_bpm
        rhr_adj = 0.0
        if rhr < 52:
            rhr_adj = -2.0
        elif rhr < 60:
            rhr_adj = -0.8
        elif rhr < 68:
            rhr_adj = 0.5
        else:
            rhr_adj = 2.0
        drivers.append({
            "name": "RHR Baseline",
            "value": rhr,
            "unit": "bpm",
            "adjustment_years": rhr_adj,
            "direction": "helping" if rhr_adj < -0.3 else ("hurting" if rhr_adj > 0.3 else "neutral"),
        })

    # Sleep consistency (±3 years) — proxy: sleep score
    if snap.sleep_score is not None:
        sleep_adj = 0.0
        if snap.sleep_score >= 85:
            sleep_adj = -2.0
        elif snap.sleep_score >= 70:
            sleep_adj = -0.5
        elif snap.sleep_score >= 55:
            sleep_adj = 0.8
        else:
            sleep_adj = 2.5
        drivers.append({
            "name": "Sleep Consistency",
            "value": snap.sleep_score,
            "unit": "",
            "adjustment_years": sleep_adj,
            "direction": "helping" if sleep_adj < -0.3 else ("hurting" if sleep_adj > 0.3 else "neutral"),
        })

    # Stress load (±2.5 years)
    if snap.stress is not None:
        stress_adj = 0.0
        if snap.stress < 25:
            stress_adj = -1.5
        elif snap.stress < 40:
            stress_adj = 0.0
        elif snap.stress < 55:
            stress_adj = 1.0
        else:
            stress_adj = 2.5
        drivers.append({
            "name": "Stress Load",
            "value": snap.stress,
            "unit": "",
            "adjustment_years": stress_adj,
            "direction": "helping" if stress_adj < -0.3 else ("hurting" if stress_adj > 0.3 else "neutral"),
        })

    # Recovery / body battery (±2 years)
    if snap.body_battery is not None:
        bb_adj = 0.0
        if snap.body_battery >= 80:
            bb_adj = -1.5
        elif snap.body_battery >= 60:
            bb_adj = -0.3
        elif snap.body_battery >= 40:
            bb_adj = 0.5
        else:
            bb_adj = 1.8
        drivers.append({
            "name": "Recovery Stability",
            "value": snap.body_battery,
            "unit": "%",
            "adjustment_years": bb_adj,
            "direction": "helping" if bb_adj < -0.3 else ("hurting" if bb_adj > 0.3 else "neutral"),
        })

    # SpO2 / Respiration (±1.5 years)
    if snap.spo2_avg is not None:
        spo2_adj = 0.0
        if snap.spo2_avg >= 97:
            spo2_adj = -1.0
        elif snap.spo2_avg >= 95:
            spo2_adj = 0.0
        elif snap.spo2_avg >= 93:
            spo2_adj = 0.8
        else:
            spo2_adj = 1.5
        drivers.append({
            "name": "SpO2 / Respiration",
            "value": snap.spo2_avg,
            "unit": "%",
            "adjustment_years": spo2_adj,
            "direction": "helping" if spo2_adj < -0.3 else ("hurting" if spo2_adj > 0.3 else "neutral"),
        })

    # Body composition (±1.5 years)
    if snap.body_fat_pct is not None:
        optimal_bf = 18 + (actual_age - 25) * 0.15
        bf_adj = round((snap.body_fat_pct - optimal_bf) * 0.06, 1)
        bf_adj = max(-1.0, min(1.5, bf_adj))
        drivers.append({
            "name": "Body Composition",
            "value": snap.body_fat_pct,
            "unit": "%",
            "adjustment_years": bf_adj,
            "direction": "helping" if bf_adj < -0.3 else ("hurting" if bf_adj > 0.3 else "neutral"),
        })

    return drivers if drivers else None
