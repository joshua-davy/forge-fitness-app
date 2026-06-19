"""Health metric schemas. Stubbed values until Garmin sync lands."""
from datetime import date as Date
from typing import List, Optional, Union
from pydantic import BaseModel


class HealthMetric(BaseModel):
    name: str
    value: Optional[Union[float, int]] = None
    unit: Optional[str] = None
    delta_7d: Optional[float] = None
    status: Optional[str] = None


class RingMetric(BaseModel):
    label: str
    value: int
    target: int = 100
    color: str


class DashboardPayload(BaseModel):
    active_date: Date
    day_progress: dict
    rings: List[RingMetric]
    metrics: List[HealthMetric]
    streak: int
    goals_total: int
    goals_completed: int
    goals_queued: int
