"""Active-date logic for Forge.

The 'active day' boundary is 6 AM local time. Before 6 AM, the active date
is still yesterday — you're winding down, not starting fresh. Centralising
this prevents drift between API, frontend, and analytics.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

ACTIVE_DAY_BOUNDARY_HOUR = 6
DEFAULT_TZ = ZoneInfo("Europe/London")


def _localise(now: datetime | None, tz: ZoneInfo) -> datetime:
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc).astimezone(tz)
    return now.astimezone(tz)


def get_active_date(now: datetime | None = None, tz: ZoneInfo = DEFAULT_TZ) -> date:
    """Return the active date for `now`. Before 6 AM local, returns yesterday."""
    local = _localise(now, tz)
    if local.hour < ACTIVE_DAY_BOUNDARY_HOUR:
        return (local - timedelta(days=1)).date()
    return local.date()


def get_tomorrow_date(now: datetime | None = None, tz: ZoneInfo = DEFAULT_TZ) -> date:
    """Return the date that 'Plan Tomorrow' should write to."""
    return get_active_date(now, tz) + timedelta(days=1)


def wake_window(
    wake_hour: int = 8,
    sleep_hour: int = 24,
    on_date: date | None = None,
    tz: ZoneInfo = DEFAULT_TZ,
) -> tuple[datetime, datetime]:
    """Return (wake_dt, sleep_dt) for the active date. Sleep hour 24 = midnight."""
    d = on_date or get_active_date(tz=tz)
    wake_dt = datetime.combine(d, time(wake_hour, 0), tzinfo=tz)
    if sleep_hour >= 24:
        sleep_dt = datetime.combine(d + timedelta(days=1), time(0, 0), tzinfo=tz)
    else:
        sleep_dt = datetime.combine(d, time(sleep_hour, 0), tzinfo=tz)
    return wake_dt, sleep_dt


def day_progress(
    now: datetime | None = None,
    wake_hour: int = 8,
    sleep_hour: int = 24,
    tz: ZoneInfo = DEFAULT_TZ,
) -> dict:
    """Compute progress through the user's waking day."""
    local = _localise(now, tz)
    wake_dt, sleep_dt = wake_window(wake_hour, sleep_hour, on_date=local.date(), tz=tz)

    if local < wake_dt:
        return {
            "percent": 0.0,
            "phase": "SLEEPING",
            "status": "Still sleeping",
            "remaining_seconds": int((wake_dt - local).total_seconds()),
            "wake_iso": wake_dt.isoformat(),
            "sleep_iso": sleep_dt.isoformat(),
            "now_iso": local.isoformat(),
        }

    if local >= sleep_dt:
        return {
            "percent": 1.0,
            "phase": "PAST BEDTIME",
            "status": "Past bedtime",
            "remaining_seconds": 0,
            "wake_iso": wake_dt.isoformat(),
            "sleep_iso": sleep_dt.isoformat(),
            "now_iso": local.isoformat(),
        }

    total = (sleep_dt - wake_dt).total_seconds()
    elapsed = (local - wake_dt).total_seconds()
    pct = max(0.0, min(1.0, elapsed / total))

    if pct < 0.20:
        phase, status = "MORNING", "Energy ramping up"
    elif pct < 0.45:
        phase, status = "MIDDAY", "Peak focus window"
    elif pct < 0.70:
        phase, status = "AFTERNOON", "Steady output"
    elif pct < 0.90:
        phase, status = "EVENING", "Wind down soon"
    else:
        phase, status = "BEDTIME", "Keep strain low now"

    return {
        "percent": pct,
        "phase": phase,
        "status": status,
        "remaining_seconds": int((sleep_dt - local).total_seconds()),
        "wake_iso": wake_dt.isoformat(),
        "sleep_iso": sleep_dt.isoformat(),
        "now_iso": local.isoformat(),
    }
