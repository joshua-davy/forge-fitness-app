"""Regression checks for the account boundary on the health API."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_TMP_DB = Path(tempfile.mkdtemp()) / "forge_private_routes.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/api/dashboard/today", None),
        ("get", "/api/profile", None),
        ("get", "/api/metrics/sleep_score", None),
        ("get", "/api/insights", None),
        ("get", "/api/special-metrics", None),
        ("get", "/api/fitness-age", None),
        ("get", "/api/biological-age", None),
        ("get", "/api/coach/today", None),
        ("get", "/api/coach/history", None),
        ("get", "/api/goals/today", None),
        ("get", "/api/sync/garmin/status", None),
        ("post", "/api/body-composition", {"weight_kg": 72}),
        ("post", "/api/coach/generate", {}),
        ("post", "/api/goals/polish", {"text": "Run easy today"}),
        ("post", "/api/sync/garmin", {}),
    ],
)
def test_private_routes_reject_anonymous_requests(method: str, path: str, payload: dict | None):
    client = TestClient(app)
    kwargs = {"json": payload} if payload is not None else {}
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == 401, response.text


def test_sync_requires_a_connection_owned_by_the_signed_in_account():
    client = TestClient(app)
    signup = client.post(
        "/api/auth/signup",
        json={"email": "sync@example.com", "password": "correct-horse-99", "display_name": "Sync User"},
    )
    assert signup.status_code == 201
    headers = {"Authorization": f"Bearer {signup.json()['token']}"}

    response = client.post("/api/sync/garmin", headers=headers)
    assert response.status_code == 409
    assert "not connected" in response.json()["detail"].lower()


def test_api_applies_baseline_security_headers():
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
