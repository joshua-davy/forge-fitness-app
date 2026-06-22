"""Goals API."""
from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.date_utils import get_active_date, get_tomorrow_date
from app.db.session import get_db
from app.api.routes.auth import current_user
from app.models.account import UserAccount
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
def goals_today(db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    return svc.list_today(db, user.id)


@router.get("/tomorrow", response_model=list[GoalOut])
def goals_tomorrow(db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    return svc.list_tomorrow(db, user.id)


@router.get("/date/{d}", response_model=list[GoalOut])
def goals_for_date(d: date, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    return svc.list_for_date(db, user.id, d)


@router.post("", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def create_goal(payload: GoalCreate, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    return svc.create(db, user.id, payload)


@router.patch("/{goal_id}", response_model=GoalOut)
def update_goal(goal_id: int, payload: GoalUpdate, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    g = svc.update(db, user.id, goal_id, payload)
    if not g:
        raise HTTPException(404, "Goal not found")
    return g


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    if not svc.delete(db, user.id, goal_id):
        raise HTTPException(404, "Goal not found")


@router.post("/reorder")
def reorder_goals(payload: ReorderRequest, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    n = svc.reorder(db, user.id, payload.items)
    return {"updated": n}


@router.post("/push-remaining", response_model=PushRemainingResponse)
def push_remaining(db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    today = get_active_date()
    tomorrow = get_tomorrow_date()
    moved = svc.push_remaining(db, user.id, today, tomorrow)
    return PushRemainingResponse(moved=moved, to_date=tomorrow)


@router.get("/streak", response_model=StreakOut)
def streak(db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    s = svc.get_streak(db, user.id)
    return StreakOut(count=s.count, last_processed_date=s.last_processed_date)


@router.post("/polish", response_model=PolishResponse)
def polish_route(payload: PolishRequest, user: UserAccount = Depends(current_user)):
    # This route can invoke the configured AI provider, so it must never be a
    # public cost-amplification endpoint.
    return polish_text(payload.text)
