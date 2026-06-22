"""Small additive schema migrations for Forge's local-first installs.

Forge started as a single-user SQLite app.  The production path now scopes
health, coach, goals, and profile data to a Forge account.  A full Alembic
history belongs in the hosted deployment, but this migration keeps existing
local databases safe while users test the multi-account flow.
"""
from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.models.goal import Goal, GoalStreak
from app.models.health import CoachSummary, HealthSnapshot, UserProfile


def _columns(engine: Engine, table: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table)}


def _add_column(engine: Engine, table: str, declaration: str) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {declaration}")


def _rebuild_health_snapshots(engine: Engine) -> None:
    """Remove the legacy unique(date) restriction without losing local rows."""
    with engine.begin() as connection:
        # SQLite retains named indexes while the legacy table is renamed. Drop
        # the old explicit indexes first so the recreated ORM table can create
        # its user/date indexes using the normal names.
        connection.exec_driver_sql("DROP INDEX IF EXISTS ix_health_snapshots_date")
        connection.exec_driver_sql("DROP INDEX IF EXISTS ix_health_snapshots_user_id")
        connection.exec_driver_sql("ALTER TABLE health_snapshots RENAME TO health_snapshots_legacy")
        HealthSnapshot.__table__.create(bind=connection, checkfirst=False)
        legacy_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(health_snapshots_legacy)")
        }
        shared_columns = [
            column.name
            for column in HealthSnapshot.__table__.columns
            if column.name not in {"user_id", "created_at", "updated_at"} and column.name in legacy_columns
        ]
        if shared_columns:
            names = ", ".join(shared_columns)
            connection.exec_driver_sql(
                f"INSERT INTO health_snapshots (user_id, {names}) "
                f"SELECT 0, {names} FROM health_snapshots_legacy"
            )
        connection.exec_driver_sql("DROP TABLE health_snapshots_legacy")


def migrate_legacy_schema(engine: Engine) -> None:
    """Upgrade prior Forge SQLite tables in place.

    Legacy records are assigned to user_id 0, a reserved non-login owner. This
    avoids accidental disclosure when a new account signs in on the same local
    database. Users can safely re-import their Garmin history after connecting.
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "health_snapshots" in tables and "user_id" not in _columns(engine, "health_snapshots"):
        if engine.dialect.name == "sqlite":
            _rebuild_health_snapshots(engine)
        else:
            _add_column(engine, "health_snapshots", "user_id INTEGER NOT NULL DEFAULT 0")

    migrations = {
        "coach_summaries": ["user_id INTEGER NOT NULL DEFAULT 0"],
        "goals": ["user_id INTEGER NOT NULL DEFAULT 0"],
        "goal_streak": ["user_id INTEGER NOT NULL DEFAULT 0"],
        "user_profiles": [
            "user_id INTEGER NOT NULL DEFAULT 0",
            "sex VARCHAR(20) NOT NULL DEFAULT 'unspecified'",
        ],
    }
    for table, declarations in migrations.items():
        if table not in tables:
            continue
        existing = _columns(engine, table)
        for declaration in declarations:
            column = declaration.split(" ", 1)[0]
            if column not in existing:
                _add_column(engine, table, declaration)

    # Existing local databases only have one profile/streak, so unique indexes
    # are safe and make user ownership durable on SQLite as well.
    current_tables = set(inspect(engine).get_table_names())
    with engine.begin() as connection:
        if "user_profiles" in current_tables:
            connection.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_user_profiles_user_id ON user_profiles (user_id)"
            )
        if "goal_streak" in current_tables:
            connection.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_goal_streak_user_id ON goal_streak (user_id)"
            )
        if "health_snapshots" in current_tables:
            connection.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_health_snapshots_user_date ON health_snapshots (user_id, date)"
            )
