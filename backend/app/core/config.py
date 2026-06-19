"""Application config from environment."""
from __future__ import annotations
import os
from datetime import date
from functools import lru_cache


class Settings:
    def __init__(self) -> None:
        self.app_name = "Forge"
        self.env = os.getenv("FORGE_ENV", "development")
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./forge.db")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.cors_origins = [
            o.strip()
            for o in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173,"
                "http://localhost:5174,http://127.0.0.1:5174,"
                "http://localhost:8081,http://127.0.0.1:8081,"
                "http://localhost:19006,http://127.0.0.1:19006",
            ).split(",")
            if o.strip()
        ]
        self.wake_hour = int(os.getenv("FORGE_WAKE_HOUR", "8"))
        self.sleep_hour = int(os.getenv("FORGE_SLEEP_HOUR", "24"))
        # Garmin credentials — stored server-side only, never sent to browser
        self.garmin_email = os.getenv("GARMIN_EMAIL", "")
        self.garmin_password = os.getenv("GARMIN_PASSWORD", "")
        # User profile for age calculations.
        # TODO: replace this with a persisted profile row. For now, use DOB rather
        # than a silent hard-coded age so Fitness/Bio age math stays honest.
        self.user_date_of_birth = os.getenv("USER_DATE_OF_BIRTH", "1999-04-03")
        self.user_birth_year = int(os.getenv("USER_BIRTH_YEAR", self.user_date_of_birth[:4]))
        self.user_height_cm = float(os.getenv("USER_HEIGHT_CM", "180"))

    def actual_age_years(self) -> float:
        try:
            dob = date.fromisoformat(self.user_date_of_birth)
        except ValueError:
            dob = date(self.user_birth_year, 1, 1)
        return round((date.today() - dob).days / 365.25, 1)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
