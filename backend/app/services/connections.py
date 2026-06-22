"""Encrypted provider-session persistence for user-owned data connections."""
from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.account import DataConnection


class ConnectionSecurityError(RuntimeError):
    """Raised when persistent provider tokens cannot be encrypted safely."""


def _key() -> bytes:
    settings = get_settings()
    if settings.connection_encryption_key:
        return settings.connection_encryption_key.encode("ascii")
    if settings.env == "production":
        raise ConnectionSecurityError(
            "FORGE_CONNECTION_ENCRYPTION_KEY must be set before provider connections can be stored."
        )

    path = Path(settings.connection_key_file)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    if path.exists():
        return path.read_bytes().strip()
    key = Fernet.generate_key()
    path.write_bytes(key + b"\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def _cipher() -> Fernet:
    try:
        return Fernet(_key())
    except (ValueError, TypeError) as exc:
        raise ConnectionSecurityError("FORGE_CONNECTION_ENCRYPTION_KEY is not a valid Fernet key.") from exc


def encrypt_token_blob(token_blob: str) -> str:
    return _cipher().encrypt(token_blob.encode("utf-8")).decode("ascii")


def decrypt_token_blob(encrypted_blob: str) -> str:
    try:
        return _cipher().decrypt(encrypted_blob.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ConnectionSecurityError("Stored Garmin session cannot be decrypted. Reconnect Garmin.") from exc


def get_connection(db: Session, user_id: int, provider: str = "garmin") -> DataConnection | None:
    return db.execute(
        select(DataConnection).where(
            DataConnection.user_id == user_id,
            DataConnection.provider == provider,
        )
    ).scalar_one_or_none()


def upsert_garmin_connection(
    db: Session,
    *,
    user_id: int,
    token_blob: str,
    external_subject: str | None,
) -> DataConnection:
    connection = get_connection(db, user_id)
    if connection is None:
        connection = DataConnection(user_id=user_id, provider="garmin")
        db.add(connection)
    connection.status = "connected"
    connection.external_subject = (external_subject or "Garmin account")[:255]
    connection.encrypted_token_blob = encrypt_token_blob(token_blob)
    connection.last_error = None
    db.commit()
    db.refresh(connection)
    return connection


def disconnect_garmin(db: Session, user_id: int) -> bool:
    connection = get_connection(db, user_id)
    if not connection:
        return False
    connection.status = "disconnected"
    connection.external_subject = None
    connection.encrypted_token_blob = None
    connection.last_error = None
    db.commit()
    return True


def public_connection_status(connection: DataConnection | None) -> dict:
    if not connection:
        return {
            "configured": False,
            "connected": False,
            "status": "not_connected",
            "account": None,
            "last_synced_at": None,
            "last_error": None,
        }
    return {
        "configured": connection.status == "connected" and bool(connection.encrypted_token_blob),
        "connected": connection.status == "connected" and bool(connection.encrypted_token_blob),
        "status": connection.status,
        "account": connection.external_subject,
        "last_synced_at": connection.last_synced_at.isoformat() if connection.last_synced_at else None,
        "last_error": connection.last_error,
    }
