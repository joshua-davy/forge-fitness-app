"""Security tests for Forge's account-owned health and Garmin connection path."""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from pathlib import Path

_TMP_DB = Path(tempfile.mkdtemp()) / "forge_account_isolation.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.core.date_utils import get_active_date  # noqa: E402
from app.main import app  # noqa: E402
from app.models.account import SyncJob  # noqa: E402
from app.models.health import HealthSnapshot  # noqa: E402
from app.services.connections import decrypt_token_blob, get_connection, upsert_garmin_connection  # noqa: E402
from app.services import garmin_sync  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def _signup(client: TestClient, email: str) -> tuple[int, dict[str, str]]:
    response = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "correct-horse-99", "display_name": email.split("@")[0]},
    )
    assert response.status_code == 201
    return response.json()["user"]["id"], {"Authorization": f"Bearer {response.json()['token']}"}


def test_health_history_is_isolated_by_account():
    client = TestClient(app)
    first_id, first_headers = _signup(client, "first@example.com")
    _, second_headers = _signup(client, "second@example.com")

    db = SessionLocal()
    try:
        db.add(HealthSnapshot(user_id=first_id, date=get_active_date(), source="garmin", steps=12345, recovery=78))
        db.commit()
    finally:
        db.close()

    first = client.get("/api/dashboard/today", headers=first_headers)
    second = client.get("/api/dashboard/today", headers=second_headers)

    assert first.status_code == 200
    assert first.json()["metrics"]["steps"] == 12345
    assert first.json()["has_garmin_data"] is True
    assert second.status_code == 200
    assert second.json()["metrics"]["steps"] is None
    assert second.json()["has_garmin_data"] is False


def test_garmin_connection_requires_the_signed_in_account(monkeypatch):
    client = TestClient(app)
    user_id, headers = _signup(client, "garmin@example.com")
    seen: dict[str, object] = {}

    def fake_connect(db, incoming_user_id, email, password):
        seen.update({"user_id": incoming_user_id, "email": email, "password": password})
        return {"status": "connected", "connected": True, "account": "Garmin Athlete", "message": "Connected"}

    monkeypatch.setattr("app.api.routes.garmin.garmin_sync.connect_user_garmin", fake_connect)

    assert client.post("/api/garmin/connect", json={"email": "x@y.com", "password": "secret-pass"}).status_code == 401
    response = client.post(
        "/api/garmin/connect",
        headers=headers,
        json={"email": "garmin@example.com", "password": "secret-pass"},
    )

    assert response.status_code == 200
    assert seen == {"user_id": user_id, "email": "garmin@example.com", "password": "secret-pass"}


def test_provider_tokens_are_encrypted_at_rest():
    db = SessionLocal()
    try:
        connection = upsert_garmin_connection(
            db,
            user_id=44,
            token_blob="opaque-garmin-token-without-password",
            external_subject="Garmin Athlete",
        )
        stored = get_connection(db, 44)
        assert stored is not None
        assert stored.encrypted_token_blob != "opaque-garmin-token-without-password"
        assert decrypt_token_blob(stored.encrypted_token_blob or "") == "opaque-garmin-token-without-password"
        assert connection.external_subject == "Garmin Athlete"
    finally:
        db.close()


def test_current_garmin_client_login_flow_persists_an_encrypted_session(monkeypatch):
    class FakeClientState:
        def dumps(self):
            return "current-client-token"

    class FakeGarmin:
        def __init__(self, email=None, password=None, return_on_mfa=False):
            self.email = email
            self.password = password
            self.return_on_mfa = return_on_mfa
            self.client = FakeClientState()
            self.display_name = "Forge Garmin"

        def login(self, tokenstore=None):
            assert tokenstore is None
            return None, None

    import garminconnect
    monkeypatch.setattr(garminconnect, "Garmin", FakeGarmin)

    db = SessionLocal()
    try:
        result = garmin_sync.connect_user_garmin(db, 9, "athlete@example.com", "correct-password")
        stored = get_connection(db, 9)
        assert result["status"] == "connected"
        assert stored is not None
        assert decrypt_token_blob(stored.encrypted_token_blob or "") == "current-client-token"
    finally:
        db.close()


def test_history_import_status_is_scoped_to_its_owner():
    client = TestClient(app)
    first_id, first_headers = _signup(client, "history-owner@example.com")
    _, second_headers = _signup(client, "history-other@example.com")
    db = SessionLocal()
    try:
        job = SyncJob(user_id=first_id, days_requested=365, total_days=365, completed_days=18, status="running")
        db.add(job)
        db.commit()
        db.refresh(job)
    finally:
        db.close()

    owner = client.get(f"/api/sync/garmin/history/jobs/{job.id}", headers=first_headers)
    other = client.get(f"/api/sync/garmin/history/jobs/{job.id}", headers=second_headers)
    assert owner.status_code == 200
    assert owner.json()["completed_days"] == 18
    assert owner.json()["progress_pct"] == 5
    assert other.status_code == 404
