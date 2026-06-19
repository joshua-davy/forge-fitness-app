"""Goals API."""
from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.date_utils import get_active_date, get_tomorrow_date
from app.db.session import get_db
from app.schemas.goal import (
    GoalCreate,
    GoalOut,
    GoalUpdate,
    PolishRequest,
    PolishResponse,
    PushRemainingResponse,
    ReorderRequest,
    StreakOut,
)
from app.services import goals as svc
from app.services.polish import polish as polish_text

router = APIRouter(prefix="/api/goals", tags=["goals"])


@router.get("/today", response_model=list[GoalOut])
def goals_today(db: Session = Depends(get_db)):
    return svc.list_today(db)


@router.get("/tomorrow", response_model=list[GoalOut])
def goals_tomorrow(db: Session = Depends(get_db)):
    return svc.list_tomorrow(db)


@router.get("/date/{d}", response_model=list[GoalOut])
def goals_for_date(d: date, db: Session = Depends(get_db)):
    return svc.list_for_date(db, d)


@router.post("", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def create_goal(payload: GoalCreate, db: Session = Depends(get_db)):
    return svc.create(db, payload)


@router.patch("/{goal_id}", response_model=GoalOut)
def update_goal(goal_id: int, payload: GoalUpdate, db: Session = Depends(get_db)):
    g = svc.update(db, goal_id, payload)
    if not g:
        raise HTTPException(404, "Goal not found")
    return g


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: int, db: Session = Depends(get_db)):
    if not svc.delete(db, goal_id):
        raise HTTPException(404, "Goal not found")


@router.post("/reorder")
def reorder_goals(payload: ReorderRequest, db: Session = Depends(get_db)):
    n = svc.reorder(db, payload.items)
    return {"updated": n}


@router.post("/push-remaining", response_model=PushRemainingResponse)
def push_remaining(db: Session = Depends(get_db)):
    today = get_active_date()
    tomorrow = get_tomorrow_date()
    moved = svc.push_remaining(db, today, tomorrow)
    return PushRemainingResponse(moved=moved, to_date=tomorrow)


@router.get("/streak", response_model=StreakOut)
def streak(db: Session = Depends(get_db)):
    s = svc.get_streak(db)
    return StreakOut(count=s.count, last_processed_date=s.last_processed_date)


@router.post("/polish", response_model=PolishResponse)
def polish_route(payload: PolishRequest):
    return polish_text(payload.text)
