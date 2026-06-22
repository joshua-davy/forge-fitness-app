"""Application configuration from environment variables."""
from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    def __init__(self) -> None:
        self.app_name = "Forge"
        self.env = os.getenv("FORGE_ENV", "development")
        self.database_url = self._normalise_database_url(os.getenv("DATABASE_URL", "sqlite:///./forge.db"))
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.cors_origins = [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173,"
                "http://localhost:5174,http://127.0.0.1:5174,"
                "http://localhost:8081,http://127.0.0.1:8081,"
                "http://localhost:19006,http://127.0.0.1:19006",
            ).split(",")
            if origin.strip()
        ]
        self.wake_hour = int(os.getenv("FORGE_WAKE_HOUR", "8"))
        self.sleep_hour = int(os.getenv("FORGE_SLEEP_HOUR", "24"))

        # Required in production to encrypt every user's Garmin tokens. In
        # development Forge creates a gitignored local key on first connection.
        self.connection_encryption_key = os.getenv("FORGE_CONNECTION_ENCRYPTION_KEY", "")
        self.connection_key_file = os.getenv("FORGE_CONNECTION_KEY_FILE", ".forge_connection.key")

    @staticmethod
    def _normalise_database_url(value: str) -> str:
        """Make Render's standard Postgres URL explicit for SQLAlchemy/psycopg."""
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value

    def validate_production_security(self) -> None:
        """Fail closed when a hosted Forge instance lacks essential safeguards."""
        if self.env.lower() != "production":
            return

        problems: list[str] = []
        if not self.connection_encryption_key:
            problems.append("FORGE_CONNECTION_ENCRYPTION_KEY is required")
        if self.database_url.startswith("sqlite"):
            problems.append("DATABASE_URL must use managed PostgreSQL, not SQLite")
        if not os.getenv("CORS_ORIGINS", "").strip():
            problems.append("CORS_ORIGINS must list the deployed web origin")
        elif any(not origin.startswith("https://") for origin in self.cors_origins):
            problems.append("CORS_ORIGINS must use HTTPS origins in production")

        if problems:
            raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
