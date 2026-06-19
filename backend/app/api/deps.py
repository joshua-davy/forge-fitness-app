"""Shared FastAPI dependencies."""
from __future__ import annotations

from typing import Iterator
from sqlalchemy.orm import Session

from ..db.session import get_db


def get_db_session() -> Iterator[Session]:
    yield from get_db()
