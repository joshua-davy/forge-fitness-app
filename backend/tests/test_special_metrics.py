"""Special derived metric tests."""
from __future__ import annotations

from datetime import date, timedelta

from app.models.health import HealthSnapshot
from app.services.special_metrics import special_metrics_from_snaps


def _snap(day: date, index: int, weekend_shift: int = 0) -> HealthSnapshot:
    bedtime_hour = 22 + weekend_shift
    wake_hour = 6 + weekend_shift
    return HealthSnapshot(
        date=day,
        source="garmin",
        recovery=68 - (index % 4),
        readiness=66 - (index % 3),
        strain=8 + (index % 5),
        target_strain=12,
        cardio_load=80 + (index % 6) * 7,
        sleep_score=78 - (index % 3),
        sleep_minutes=455,
        sleep_deep_minutes=80,
        sleep_rem_minutes=105,
        sleep_light_minutes=270,
        sleep_awake_minutes=18,
        sleep_debt_minutes=35,
        sleep_need_minutes=490,
        sleep_start_local=f"{day.isoformat()}T{bedtime_hour:02d}:30:00",
        sleep_end_local=f"{(day + timedelta(days=1)).isoformat()}T{wake_hour:02d}:15:00",
        hrv_ms=55 - (index % 5),
        hrv_baseline_ms=54,
        rhr_bpm=56 + (index % 4),
        rhr_baseline_bpm=57,
        body_battery=62 - (index % 5),
        stress=28 + (index % 6),
        spo2_avg=96,
        respiration_avg=14.2 + (index % 3) * 0.1,
        steps=8500 + index * 30,
        active_minutes=35,
    )


def test_special_metrics_return_scored_and_limited_payloads():
    start = date(2026, 4, 1)
    snaps = []
    for index in range(35):
        day = start + timedelta(days=index)
        weekend_shift = 1 if day.weekday() >= 5 else 0
        snaps.append(_snap(day, index, weekend_shift=weekend_shift))

    body = special_metrics_from_snaps(snaps, start + timedelta(days=34))

    assert body["sleep_regularity"]["score"] is not None
    assert body["social_jetlag"]["value"] >= 1
    assert body["training_gate"]["value"] in {
        "Rest only",
        "Easy aerobic",
        "Moderate available",
        "Intensity available",
    }
    assert body["physiological_anomaly_load"]["score"] is not None
    assert "aerobic_decoupling" not in body


def test_special_metrics_handle_empty_history_without_faking_scores():
    body = special_metrics_from_snaps([])

    assert body["sleep_regularity"]["score"] is None
    assert body["sleep_regularity"]["status"] == "no_data"
    assert body["training_gate"]["summary"]
    assert "dfa_alpha1_threshold" not in body
