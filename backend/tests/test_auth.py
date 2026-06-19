"""Auth foundation tests."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_TMP_DB = Path(tempfile.mkdtemp()) / "forge_auth_test.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DB}")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.db.session import Base, engine
from app.main import app


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_signup_returns_bearer_token_and_me_works():
    client = TestClient(app)
    res = client.post(
        "/api/auth/signup",
        json={"email": "JOSH@example.com", "password": "correct-horse-99", "display_name": "Joshua"},
    )
    assert res.status_code == 201
    payload = res.json()
    assert payload["token_type"] == "bearer"
    assert payload["token"]
    assert payload["user"]["email"] == "josh@example.com"
    assert payload["user"]["display_name"] == "Joshua"

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {payload['token']}"})
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "josh@example.com"


def test_duplicate_signup_is_blocked():
    client = TestClient(app)
    body = {"email": "dupe@example.com", "password": "correct-horse-99", "display_name": "One"}
    assert client.post("/api/auth/signup", json=body).status_code == 201
    assert client.post("/api/auth/signup", json=body).status_code == 409


def test_login_and_logout_revokes_session():
    client = TestClient(app)
    body = {"email": "login@example.com", "password": "correct-horse-99", "display_name": "Login"}
    assert client.post("/api/auth/signup", json=body).status_code == 201

    bad = client.post("/api/auth/login", json={"email": body["email"], "password": "wrong"})
    assert bad.status_code == 401

    good = client.post("/api/auth/login", json={"email": body["email"], "password": body["password"]})
    assert good.status_code == 200
    token = good.json()["token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_me_requires_token():
    client = TestClient(app)
    assert client.get("/api/auth/me").status_code == 401
