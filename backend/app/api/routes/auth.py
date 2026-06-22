"""Authentication and account routes.

These endpoints are the foundation for a real hosted Forge userbase. Existing
local dashboard endpoints remain available while we migrate metric data to
strict user ownership.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import AuditLog, UserAccount
from app.models.health import UserProfile
from app.services.security import (
    create_session,
    get_user_by_token,
    hash_password,
    normalize_email,
    revoke_token,
    verify_password,
)
from app.services.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignupInput(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=200)
    display_name: str = Field(default="Forge Athlete", min_length=1, max_length=120)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        email = normalize_email(value)
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address")
        return email


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        email = normalize_email(value)
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address")
        return email


class AuthPayload(BaseModel):
    token: str
    token_type: str = "bearer"
    user: dict


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> UserAccount:
    token = _bearer_token(authorization)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    user = get_user_by_token(db, token)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")
    return user


def _user_payload(user: UserAccount) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "email_verified": user.email_verified_at is not None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _audit(db: Session, event_type: str, detail: str, user_id: int | None = None) -> None:
    db.add(AuditLog(user_id=user_id, event_type=event_type, detail=detail[:2000]))


@router.post("/signup", response_model=AuthPayload, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupInput, request: Request, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    enforce_rate_limit(f"signup:{request.client.host if request.client else 'unknown'}:{email}", limit=4, window_seconds=3600)
    existing = db.execute(select(UserAccount).where(UserAccount.email == email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account already exists for this email")

    user = UserAccount(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name.strip() or "Forge Athlete",
    )
    db.add(user)
    db.flush()
    db.add(UserProfile(user_id=user.id, name=user.display_name))
    _audit(db, "auth.signup", f"Created account for {email}", user.id)
    db.commit()
    db.refresh(user)
    token, _ = create_session(
        db,
        user,
        user_agent=request.headers.get("user-agent"),
        ip_hint=request.client.host if request.client else None,
    )
    return AuthPayload(token=token, user=_user_payload(user))


@router.post("/login", response_model=AuthPayload)
def login(payload: LoginInput, request: Request, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    enforce_rate_limit(f"login:{request.client.host if request.client else 'unknown'}:{email}", limit=8, window_seconds=900)
    user = db.execute(select(UserAccount).where(UserAccount.email == email)).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        _audit(db, "auth.login_failed", f"Failed login for {email}")
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")
    _audit(db, "auth.login", f"Session created for {email}", user.id)
    db.commit()
    token, _ = create_session(
        db,
        user,
        user_agent=request.headers.get("user-agent"),
        ip_hint=request.client.host if request.client else None,
    )
    return AuthPayload(token=token, user=_user_payload(user))


@router.get("/me")
def me(user: UserAccount = Depends(current_user)):
    return {"user": _user_payload(user)}


@router.post("/logout")
def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    token = _bearer_token(authorization)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    revoked = revoke_token(db, token)
    if not revoked:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")
    return {"ok": True}
