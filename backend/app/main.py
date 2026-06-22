"""Forge backend."""
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import auth, dashboard, garmin, goals, planning
from app.core.config import get_settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_settings().validate_production_security()
    init_db()
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Forge API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if s.env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
    app.include_router(auth.router)
    app.include_router(goals.router)
    app.include_router(dashboard.router)
    app.include_router(garmin.router)
    app.include_router(planning.router)

    @app.get("/")
    def root():
        return {"app": s.app_name, "env": s.env, "status": "ok"}

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    return app


app = create_app()
