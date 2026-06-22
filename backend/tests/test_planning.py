from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import Base, SessionLocal, engine
from app.main import app
from app.models.account import Workout
from app.models.health import HealthSnapshot, UserProfile
from app.services import planning


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed(db, user_id: int = 91):
    today = date.today()
    profile = db.execute(select(UserProfile).where(UserProfile.user_id == user_id)).scalar_one_or_none()
    if profile is None:
        db.add(UserProfile(user_id=user_id, name="Planner", date_of_birth=date(1999, 4, 3), sex="male", height_cm=180))
    else:
        profile.date_of_birth = date(1999, 4, 3)
        profile.sex = "male"
        profile.height_cm = 180
    for index in range(30):
        day = today - timedelta(days=29 - index)
        db.add(HealthSnapshot(
            user_id=user_id, date=day, source="garmin", weight_kg=78, active_calories=450,
            sleep_score=72 + (index % 8), sleep_start_local=f"{day.isoformat()}T22:{20 + index % 3:02d}:00",
            sleep_end_local=f"{(day + timedelta(days=1)).isoformat()}T06:30:00",
            sleep_deep_minutes=80, sleep_rem_minutes=100,
        ))
    for index in range(8):
        day = today - timedelta(days=index * 3)
        db.add(Workout(
            user_id=user_id, provider_activity_id=f"run-{index}", activity_date=day,
            activity_type="running", duration_minutes=25 + index, distance_km=5 + index * 0.3,
            average_hr=150, calories=420,
        ))
    db.commit()
    return today


def test_nutrition_uses_weight_goal_and_activity(db):
    today = _seed(db)
    planning.update_planning_settings(db, 91, {"body_goal": "lose_fat"})
    payload = planning.nutrition_plan(db, 91, today)
    assert payload["status"] == "ready"
    assert payload["protein_g"]["low"] >= 140
    assert payload["energy_kcal"]["goal_adjustment"] < 0


def test_sleep_explorer_filters_bedtime_and_activity(db):
    today = _seed(db)
    payload = planning.sleep_explorer(db, 91, today, 30, 22 * 60, 23 * 60 + 59, "running", 20)
    assert payload["summary"]["nights"] > 0
    assert all(point["workout_types"] == ["running"] for point in payload["points"])


def test_fitness_predictions_need_comparable_workouts(db):
    today = _seed(db)
    payload = planning.fitness_predictions(db, 91, today)
    assert payload["running"][0]["estimate_seconds"] is not None
    assert payload["cycling"][0]["estimate_seconds"] is None


def test_planning_endpoints_are_private_and_user_scoped():
    client = TestClient(app)
    created = client.post("/api/auth/signup", json={
        "email": "planning@example.com", "password": "correct-horse-99", "display_name": "Planner",
    })
    assert created.status_code == 201
    user_id = created.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {created.json()['token']}"}
    db = SessionLocal()
    try:
        _seed(db, user_id)
    finally:
        db.close()
    assert client.get("/api/planning/nutrition", headers=headers).status_code == 200
    assert client.get("/api/planning/sleep-explorer?activity_kind=running", headers=headers).status_code == 200
    assert client.get("/api/planning/fitness-predictions", headers=headers).status_code == 200
    saved = client.put("/api/planning", headers=headers, json={"body_goal": "gain_muscle", "work_start": "09:00"})
    assert saved.status_code == 200
    assert saved.json()["body_goal"] == "gain_muscle"
