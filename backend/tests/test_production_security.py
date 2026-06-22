import pytest

from app.core.config import Settings


def test_production_rejects_sqlite_and_missing_token_key(monkeypatch):
    monkeypatch.setenv("FORGE_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./forge.db")
    monkeypatch.delenv("FORGE_CONNECTION_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        Settings().validate_production_security()


def test_production_accepts_secure_postgres_configuration(monkeypatch):
    monkeypatch.setenv("FORGE_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://forge:secret@db.example/forge")
    monkeypatch.setenv("FORGE_CONNECTION_ENCRYPTION_KEY", "x" * 44)
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")

    Settings().validate_production_security()


def test_render_postgres_url_uses_psycopg_driver(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://forge:secret@db.example/forge")
    assert Settings().database_url == "postgresql+psycopg://forge:secret@db.example/forge"
