"""Small security helpers for Forge accounts.

This keeps auth dependency-light for the prototype. Production can later swap
the session backend to managed auth without changing route contracts.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import AuthSession, UserAccount

# OWASP's current PBKDF2-HMAC-SHA256 guidance is at least 600k iterations.
# Stored hashes retain their iteration count so existing local accounts remain
# valid while new or changed passwords receive the stronger work factor.
PBKDF2_ITERATIONS = 600_000
SESSION_DAYS = 30


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_s, salt_s, digest_s = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_s)
        salt = base64.urlsafe_b64decode(salt_s.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_s.encode("ascii"))
    except Exception:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(
    db: Session,
    user: UserAccount,
    *,
    user_agent: str | None = None,
    ip_hint: str | None = None,
) -> tuple[str, AuthSession]:
    token = secrets.token_urlsafe(40)
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(token),
        user_agent=(user_agent or "")[:500] or None,
        ip_hint=(ip_hint or "")[:80] or None,
        expires_at=utcnow() + timedelta(days=SESSION_DAYS),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return token, session


def get_user_by_token(db: Session, token: str) -> UserAccount | None:
    session = db.execute(
        select(AuthSession).where(AuthSession.token_hash == hash_token(token))
    ).scalar_one_or_none()
    if not session or session.revoked_at is not None or _as_aware(session.expires_at) <= utcnow():
        return None
    return db.execute(
        select(UserAccount).where(UserAccount.id == session.user_id, UserAccount.is_active.is_(True))
    ).scalar_one_or_none()


def revoke_token(db: Session, token: str) -> bool:
    session = db.execute(
        select(AuthSession).where(AuthSession.token_hash == hash_token(token))
    ).scalar_one_or_none()
    if not session or session.revoked_at is not None:
        return False
    session.revoked_at = utcnow()
    db.commit()
    return True
