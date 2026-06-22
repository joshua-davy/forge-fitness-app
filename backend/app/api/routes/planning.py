"""User-owned planning, fuel, sleep-explorer, and forecast endpoints."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.routes.auth import current_user
from app.db.session import get_db
from app.models.account import UserAccount
from app.services import planning


router = APIRouter(prefix="/api/planning", tags=["planning"])


class PlanningInput(BaseModel):
    body_goal: str | None = Field(default=None, pattern="^(maintain|lose_weight|gain_weight|gain_muscle|lose_fat)$")
    work_start: str | None = Field(default=None, max_length=5)
    work_end: str | None = Field(default=None, max_length=5)
    commute_minutes: int | None = Field(default=None, ge=0, le=240)
    preferred_wake: str | None = Field(default=None, max_length=5)
    desired_sleep_hours: float | None = Field(default=None, ge=5, le=10)
    hidden_cards: list[str] | None = None


@router.get("")
def get_planning(db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    return planning.planning_settings_payload(db, user.id)


@router.put("")
def update_planning(payload: PlanningInput, db: Session = Depends(get_db), user: UserAccount = Depends(current_user)):
    try:
        return planning.update_planning_settings(db, user.id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/nutrition")
def get_nutrition_plan(
    selected_date: date | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_user),
):
    return planning.nutrition_plan(db, user.id, selected_date or date.today())


@router.get("/sleep-schedule")
def get_sleep_schedule(
    selected_date: date | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_user),
):
    return planning.sleep_schedule(db, user.id, selected_date or date.today())


@router.get("/sleep-explorer")
def get_sleep_explorer(
    days: int = Query(90, ge=14, le=365),
    bedtime_from: str | None = Query(None, max_length=5),
    bedtime_to: str | None = Query(None, max_length=5),
    activity_kind: str | None = Query(None, pattern="^(running|cycling|strength|other)$"),
    min_duration: int | None = Query(None, ge=0, le=600),
    selected_date: date | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_user),
):
    try:
        return planning.sleep_explorer(
            db, user.id, selected_date or date.today(), days,
            planning._parse_clock(bedtime_from), planning._parse_clock(bedtime_to), activity_kind, min_duration,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/fitness-predictions")
def get_fitness_predictions(
    selected_date: date | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
    user: UserAccount = Depends(current_user),
):
    return planning.fitness_predictions(db, user.id, selected_date or date.today())
