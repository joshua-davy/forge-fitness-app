"""Goal service: CRUD, reorder, push-remaining, streak rollover.

Streak rule: increments only when a day had >=1 goal and all completed.
Days with zero goals neither break nor extend the streak.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.date_utils import get_active_date, get_tomorrow_date
from app.models.goal import Goal, GoalStreak
from app.schemas.goal import GoalCreate, GoalUpdate, ReorderItem


# ---------- CRUD ----------

def list_for_date(db: Session, user_id: int, d: date) -> list[Goal]:
    stmt = (
        select(Goal)
        .where(Goal.user_id == user_id, Goal.date == d)
        .order_by(Goal.sort_order.asc(), Goal.id.asc())
    )
    return list(db.execute(stmt).scalars().all())


def list_today(db: Session, user_id: int, now: datetime | None = None) -> list[Goal]:
    return list_for_date(db, user_id, get_active_date(now))


def list_tomorrow(db: Session, user_id: int, now: datetime | None = None) -> list[Goal]:
    return list_for_date(db, user_id, get_tomorrow_date(now))


def _next_sort_order(db: Session, user_id: int, d: date) -> int:
    existing = list_for_date(db, user_id, d)
    return (max((g.sort_order for g in existing), default=-1)) + 1


def create(db: Session, user_id: int, payload: GoalCreate, now: datetime | None = None) -> Goal:
    d = payload.date or get_active_date(now)
    g = Goal(
        user_id=user_id,
        date=d,
        text=payload.text.strip(),
        queued=payload.queued,
        sort_order=_next_sort_order(db, user_id, d),
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


def get(db: Session, user_id: int, goal_id: int) -> Goal | None:
    return db.execute(
        select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
    ).scalar_one_or_none()


def update(db: Session, user_id: int, goal_id: int, payload: GoalUpdate) -> Goal | None:
    g = get(db, user_id, goal_id)
    if not g:
        return None
    if payload.text is not None:
        g.text = payload.text.strip()
    if payload.done is not None and payload.done != g.done:
        g.done = payload.done
        g.done_at = datetime.now(timezone.utc) if payload.done else None
    if payload.queued is not None:
        g.queued = payload.queued
    if payload.sort_order is not None:
        g.sort_order = payload.sort_order
    db.commit()
    db.refresh(g)
    _maybe_advance_streak(db, user_id, g.date)
    return g


def delete(db: Session, user_id: int, goal_id: int) -> bool:
    g = get(db, user_id, goal_id)
    if not g:
        return False
    d = g.date
    db.delete(g)
    db.commit()
    _maybe_advance_streak(db, user_id, d)
    return True


def reorder(db: Session, user_id: int, items: list[ReorderItem]) -> int:
    n = 0
    for it in items:
        g = get(db, user_id, it.id)
        if g:
            g.sort_order = it.sort_order
            n += 1
    db.commit()
    return n


def push_remaining(db: Session, user_id: int, from_date: date, to_date: date) -> int:
    """Move all unfinished goals from from_date to to_date."""
    goals = [g for g in list_for_date(db, user_id, from_date) if not g.done]
    if not goals:
        return 0
    base = _next_sort_order(db, user_id, to_date)
    for i, g in enumerate(goals):
        g.date = to_date
        g.sort_order = base + i
        g.queued = False
    db.commit()
    return len(goals)


# ---------- Streak ----------

def _get_or_create_streak(db: Session, user_id: int) -> GoalStreak:
    s = db.execute(select(GoalStreak).where(GoalStreak.user_id == user_id)).scalar_one_or_none()
    if not s:
        s = GoalStreak(user_id=user_id, count=0, last_processed_date=None)
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def _maybe_advance_streak(db: Session, user_id: int, d: date) -> None:
    goals = list_for_date(db, user_id, d)
    if not goals or not all(g.done for g in goals):
        return
    s = _get_or_create_streak(db, user_id)
    if s.last_processed_date == d:
        return
    if s.last_processed_date is None or d > s.last_processed_date:
        s.count += 1
        s.last_processed_date = d
        db.commit()


def get_streak(db: Session, user_id: int) -> GoalStreak:
    return _get_or_create_streak(db, user_id)


# ---------- Analytics ----------

def daily_completion_stats(db: Session, user_id: int, d: date) -> dict:
    goals = list_for_date(db, user_id, d)
    total = len(goals)
    completed = sum(1 for g in goals if g.done)
    queued = sum(1 for g in goals if g.queued and not g.done)
    rate = (completed / total) if total else None
    return {
        "date": d.isoformat(),
        "total": total,
        "completed": completed,
        "queued": queued,
        "completion_rate": rate,
    }


def completion_rate_window(db: Session, user_id: int, end: date, days: int = 7) -> dict:
    rates = []
    for i in range(days):
        d = end - timedelta(days=i)
        s = daily_completion_stats(db, user_id, d)
        if s["total"]:
            rates.append(s["completion_rate"])
    avg = sum(rates) / len(rates) if rates else None
    return {"window_days": days, "days_with_goals": len(rates), "avg_rate": avg}
