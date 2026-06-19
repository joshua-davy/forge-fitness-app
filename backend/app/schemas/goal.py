"""Pydantic v2 schemas for the goals API."""
from datetime import date as Date, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class GoalBase(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    queued: bool = False


class GoalCreate(GoalBase):
    date: Optional[Date] = None


class GoalUpdate(BaseModel):
    text: Optional[str] = Field(default=None, min_length=1, max_length=500)
    done: Optional[bool] = None
    queued: Optional[bool] = None
    sort_order: Optional[int] = None


class GoalOut(GoalBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: Date
    done: bool
    done_at: Optional[datetime] = None
    sort_order: int
    created_at: datetime
    updated_at: datetime


class ReorderItem(BaseModel):
    id: int
    sort_order: int


class ReorderRequest(BaseModel):
    items: List[ReorderItem]


class PushRemainingResponse(BaseModel):
    moved: int
    to_date: Date


class StreakOut(BaseModel):
    count: int
    last_processed_date: Optional[Date] = None


class PolishRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class PolishResponse(BaseModel):
    text: str
    original: str
    used_ai: bool
    warning: Optional[str] = None
