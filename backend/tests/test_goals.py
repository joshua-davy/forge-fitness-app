"""Backend tests: date logic, goals CRUD, streak, push-remaining, API smoke."""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_TMP_DB = Path(tempfile.mkdtemp()) / "forge_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.date_utils import get_active_date, get_tomorrow_date, day_progress  # noqa: E402
from app.db.session import Base, engine, SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.goal import GoalCreate, GoalUpdate, ReorderItem  # noqa: E402
from app.services import goals as svc  # noqa: E402


TZ = ZoneInfo("Europe/London")
USER_ID = 1


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def test_active_date_before_6am_returns_yesterday():
    now = datetime(2026, 5, 19, 3, 0, tzinfo=TZ)
    assert get_active_date(now) == date(2026, 5, 18)


def test_active_date_at_6am_returns_today():
    now = datetime(2026, 5, 19, 6, 0, tzinfo=TZ)
    assert get_active_date(now) == date(2026, 5, 19)


def test_active_date_evening_returns_today():
    now = datetime(2026, 5, 19, 22, 0, tzinfo=TZ)
    assert get_active_date(now) == date(2026, 5, 19)


def test_tomorrow_after_6am():
    now = datetime(2026, 5, 19, 9, 0, tzinfo=TZ)
    assert get_tomorrow_date(now) == date(2026, 5, 20)


def test_tomorrow_before_6am():
    now = datetime(2026, 5, 19, 3, 0, tzinfo=TZ)
    assert get_tomorrow_date(now) == date(2026, 5, 19)


def test_day_progress_midday():
    now = datetime(2026, 5, 19, 14, 0, tzinfo=TZ)
    p = day_progress(now, wake_hour=8, sleep_hour=24)
    assert abs(p["percent"] - 0.375) < 0.01


def test_day_progress_sleeping():
    now = datetime(2026, 5, 19, 6, 30, tzinfo=TZ)
    p = day_progress(now, wake_hour=8, sleep_hour=24)
    assert p["percent"] == 0.0
    assert p["phase"] == "SLEEPING"


def test_create_and_list_today(db):
    g = svc.create(db, USER_ID, GoalCreate(text="Train legs"))
    assert g.id and g.text == "Train legs"
    assert not g.done
    assert len(svc.list_today(db, USER_ID)) == 1


def test_complete_goal_sets_done_at(db):
    g = svc.create(db, USER_ID, GoalCreate(text="Walk dog"))
    updated = svc.update(db, USER_ID, g.id, GoalUpdate(done=True))
    assert updated.done is True
    assert updated.done_at is not None


def test_reorder(db):
    a = svc.create(db, USER_ID, GoalCreate(text="A"))
    b = svc.create(db, USER_ID, GoalCreate(text="B"))
    c = svc.create(db, USER_ID, GoalCreate(text="C"))
    svc.reorder(db, USER_ID, [ReorderItem(id=c.id, sort_order=0),
                     ReorderItem(id=a.id, sort_order=1),
                     ReorderItem(id=b.id, sort_order=2)])
    ordered = svc.list_today(db, USER_ID)
    assert [g.text for g in ordered] == ["C", "A", "B"]


def test_streak_increments_when_all_complete(db):
    today = get_active_date()
    a = svc.create(db, USER_ID, GoalCreate(text="A"))
    b = svc.create(db, USER_ID, GoalCreate(text="B"))
    svc.update(db, USER_ID, a.id, GoalUpdate(done=True))
    svc.update(db, USER_ID, b.id, GoalUpdate(done=True))
    s = svc.get_streak(db, USER_ID)
    assert s.count == 1
    assert s.last_processed_date == today


def test_streak_does_not_double_count(db):
    a = svc.create(db, USER_ID, GoalCreate(text="A"))
    svc.update(db, USER_ID, a.id, GoalUpdate(done=True))
    svc.update(db, USER_ID, a.id, GoalUpdate(text="A renamed"))
    assert svc.get_streak(db, USER_ID).count == 1


def test_streak_zero_goal_day_does_not_advance(db):
    assert svc.get_streak(db, USER_ID).count == 0


def test_push_remaining_moves_only_unfinished(db):
    today = get_active_date()
    tomorrow = get_tomorrow_date()
    a = svc.create(db, USER_ID, GoalCreate(text="Done"))
    svc.create(db, USER_ID, GoalCreate(text="Pending 1"))
    svc.create(db, USER_ID, GoalCreate(text="Pending 2"))
    svc.update(db, USER_ID, a.id, GoalUpdate(done=True))
    moved = svc.push_remaining(db, USER_ID, today, tomorrow)
    assert moved == 2
    assert len(svc.list_for_date(db, USER_ID, today)) == 1
    assert len(svc.list_for_date(db, USER_ID, tomorrow)) == 2


def test_completion_rate(db):
    a = svc.create(db, USER_ID, GoalCreate(text="A"))
    svc.create(db, USER_ID, GoalCreate(text="B"))
    svc.update(db, USER_ID, a.id, GoalUpdate(done=True))
    stats = svc.daily_completion_stats(db, USER_ID, get_active_date())
    assert stats["total"] == 2 and stats["completed"] == 1
    assert stats["completion_rate"] == 0.5


def test_api_smoke_full_flow():
    client = TestClient(app)
    assert client.get("/healthz").status_code == 200
    auth = client.post("/api/auth/signup", json={"email": "goals@example.com", "password": "correct-horse-99", "display_name": "Goals"})
    assert auth.status_code == 201
    headers = {"Authorization": f"Bearer {auth.json()['token']}"}

    r = client.post("/api/goals", json={"text": "Run 5k"}, headers=headers)
    assert r.status_code == 201
    gid = r.json()["id"]

    assert len(client.get("/api/goals/today", headers=headers).json()) == 1

    r = client.patch(f"/api/goals/{gid}", json={"done": True}, headers=headers)
    assert r.json()["done"] is True
    assert client.get("/api/goals/streak", headers=headers).json()["count"] == 1

    body = client.get("/api/dashboard/today", headers=headers).json()
    assert body["goals_total"] == 1 and body["goals_completed"] == 1
    assert len(body["rings"]) == 3

    coach = client.get("/api/coach/today", headers=headers).json()
    assert "observations" in coach or "headline" in coach


def test_polish_degrades_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from app.core import config
    config.get_settings.cache_clear()
    client = TestClient(app)
    auth = client.post(
        "/api/auth/signup",
        json={"email": "polish@example.com", "password": "correct-horse-99", "display_name": "Polish"},
    )
    assert auth.status_code == 201
    r = client.post(
        "/api/goals/polish",
        json={"text": "do gym later"},
        headers={"Authorization": f"Bearer {auth.json()['token']}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["used_ai"] is False
    assert body["text"] == "do gym later"
    assert body["warning"]
