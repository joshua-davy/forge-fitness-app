"""Historical analytics API tests."""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

_TMP_DB = Path(tempfile.mkdtemp()) / "forge_insights_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.health import HealthSnapshot  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def seed_history(days: int = 30) -> None:
    today = date.today()
    db = SessionLocal()
    try:
        for index in range(days):
            d = today - timedelta(days=days - index - 1)
            db.add(
                HealthSnapshot(
                    user_id=1,
                    date=d,
                    source="garmin",
                    recovery=58 + index * 0.7,
                    readiness=56 + index * 0.5,
                    strain=8 + (index % 5),
                    target_strain=12,
                    sleep_score=62 + index * 0.4,
                    sleep_minutes=420 + index,
                    sleep_debt_minutes=max(0, 90 - index),
                    sleep_need_minutes=480,
                    sleep_start_local=f"{d.isoformat()}T22:{index % 6}0:00",
                    sleep_end_local=f"{(d + timedelta(days=1)).isoformat()}T06:{index % 4}0:00",
                    sleep_deep_minutes=78 + (index % 12),
                    sleep_rem_minutes=96 + (index % 10),
                    sleep_light_minutes=240 + (index % 15),
                    hrv_ms=44 + index * 0.8,
                    hrv_baseline_ms=52,
                    rhr_bpm=64 - index * 0.15,
                    rhr_baseline_bpm=60,
                    body_battery=44 + index,
                    stress=58 - index * 0.6,
                    spo2_avg=96,
                    respiration_avg=14,
                    steps=7000 + index * 120,
                    active_calories=360 + index * 5,
                    vo2max=43 + index * 0.05,
                    cardio_load=55 + index,
                    load_balance=1.0,
                    weight_kg=78,
                    body_fat_pct=18,
                    fitness_age=29 - index * 0.03,
                    biological_age=30 - index * 0.02,
                )
            )
        db.commit()
    finally:
        db.close()


def test_metric_detail_payload_contains_history_intelligence():
    seed_history()
    client = TestClient(app)
    auth = client.post("/api/auth/signup", json={"email": "insights-one@example.com", "password": "correct-horse-99", "display_name": "Insights"})
    assert auth.status_code == 201
    headers = {"Authorization": f"Bearer {auth.json()['token']}"}

    response = client.get("/api/metrics/hrv?range=30d", headers=headers)
    assert response.status_code == 200
    body = response.json()

    assert body["metric"] == "hrv"
    assert body["coverage"]["covered_days"] == 30
    assert len(body["series"]) == 30
    assert len(body["moving_avg_7d"]) == 30
    assert body["stats"]["trend"] in {"improving", "declining", "stable"}
    assert "flags" in body
    assert body["insights"][0]["metric"] == "hrv"
    assert isinstance(body["correlations"], list)


def test_dashboard_insights_returns_flags_insights_and_patterns():
    seed_history()
    client = TestClient(app)
    auth = client.post("/api/auth/signup", json={"email": "insights-two@example.com", "password": "correct-horse-99", "display_name": "Insights"})
    assert auth.status_code == 201
    headers = {"Authorization": f"Bearer {auth.json()['token']}"}

    response = client.get("/api/insights?range=30d", headers=headers)
    assert response.status_code == 200
    body = response.json()

    assert body["range"] == "30d"
    assert "flags" in body
    assert len(body["insights"]) >= 3
    assert {p["id"] for p in body["patterns"]} >= {
        "best_bedtime",
        "training_recovery_lag",
        "stress_recovery",
    }


def test_derived_sleep_metric_has_its_own_history_series():
    seed_history()
    client = TestClient(app)
    auth = client.post("/api/auth/signup", json={"email": "insights-three@example.com", "password": "correct-horse-99", "display_name": "Insights"})
    assert auth.status_code == 201
    headers = {"Authorization": f"Bearer {auth.json()['token']}"}

    response = client.get("/api/metrics/sleep_regularity?range=30d", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["metric"] == "sleep_regularity"
    assert body["label"] == "Sleep Regularity"
    assert body["stats"]["count"] > 0
    assert body["explanation"].endswith("not a proxy chart for Sleep Score.")
