"""Regression test for upgrading the original single-user SQLite schema."""
from __future__ import annotations

from sqlalchemy import create_engine, text

from app.db.migrations import migrate_legacy_schema


def test_legacy_health_rows_are_quarantined_during_account_migration(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE health_snapshots ("
            "id INTEGER PRIMARY KEY, date DATE NOT NULL UNIQUE, steps INTEGER, "
            "source VARCHAR(32) NOT NULL, created_at DATETIME, updated_at DATETIME)"
        ))
        connection.execute(text(
            "INSERT INTO health_snapshots (id, date, steps, source) "
            "VALUES (1, '2026-06-01', 9000, 'garmin')"
        ))

    migrate_legacy_schema(engine)

    with engine.connect() as connection:
        row = connection.execute(text(
            "SELECT user_id, date, steps, source FROM health_snapshots"
        )).mappings().one()
        assert row["user_id"] == 0
        assert str(row["date"]) == "2026-06-01"
        assert row["steps"] == 9000
        assert row["source"] == "garmin"

        indexes = connection.execute(text("PRAGMA index_list(health_snapshots)")).mappings().all()
        assert any(index["name"] == "ix_health_snapshots_user_date" for index in indexes)
