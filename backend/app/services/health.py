"""Health metric provider.

Currently produces deterministic stubbed values seeded by date so the UI
looks alive without Garmin sync. When Garmin OAuth lands, replace this
module's body — the contract stays the same.
"""
from __future__ import annotations

import hashlib
from datetime import date

from app.schemas.health import HealthMetric, RingMetric


def _seed(d: date, key: str) -> float:
    """Deterministic 0..1 value for (date, key)."""
    h = hashlib.sha256(f"{d.isoformat()}::{key}".encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def _v(d: date, key: str, lo: float, hi: float) -> float:
    return lo + (hi - lo) * _seed(d, key)


def rings_for(d: date) -> list[RingMetric]:
    recovery = int(_v(d, "recovery", 45, 92))
    readiness = int(_v(d, "readiness", 40, 95))
    strain_target = int(_v(d, "strain", 35, 90))
    return [
        RingMetric(label="Recovery", value=recovery, color="--ring-recovery"),
        RingMetric(label="Readiness", value=readiness, color="--ring-readiness"),
        RingMetric(label="Strain target", value=strain_target, color="--ring-strain"),
    ]


def metrics_for(d: date) -> list[HealthMetric]:
    sleep_hrs = round(_v(d, "sleep", 5.5, 8.6), 1)
    hrv = int(_v(d, "hrv", 38, 88))
    rhr = int(_v(d, "rhr", 46, 62))
    bb = int(_v(d, "bb", 25, 95))
    stress = int(_v(d, "stress", 18, 62))

    def status(val: float, good: tuple, warn: tuple) -> str:
        if good[0] <= val <= good[1]:
            return "good"
        if warn[0] <= val <= warn[1]:
            return "warn"
        return "bad"

    return [
        HealthMetric(
            name="Sleep",
            value=sleep_hrs,
            unit="h",
            delta_7d=round(_v(d, "sleep_d", -1.0, 1.0), 1),
            status=status(sleep_hrs, (7.0, 9.0), (6.0, 9.5)),
        ),
        HealthMetric(
            name="HRV",
            value=hrv,
            unit="ms",
            delta_7d=round(_v(d, "hrv_d", -8, 8), 1),
            status=status(hrv, (55, 100), (45, 100)),
        ),
        HealthMetric(
            name="Resting HR",
            value=rhr,
            unit="bpm",
            delta_7d=round(_v(d, "rhr_d", -3, 3), 1),
            status="good" if rhr < 55 else "warn",
        ),
        HealthMetric(
            name="Body Battery",
            value=bb,
            unit="%",
            delta_7d=round(_v(d, "bb_d", -10, 10), 1),
            status=status(bb, (65, 100), (40, 100)),
        ),
        HealthMetric(
            name="Stress",
            value=stress,
            unit="",
            delta_7d=round(_v(d, "stress_d", -10, 10), 1),
            status=status(stress, (0, 30), (0, 50)),
        ),
    ]
