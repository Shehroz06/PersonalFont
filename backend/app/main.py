"""FastAPI application entry point (spec §14).

Run locally with:
    backend/.venv/bin/uvicorn app.main:app --reload --app-dir backend
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.character_set import router as character_set_router
from app.api.jobs import router as jobs_router
from app.api.templates import router as templates_router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="PersonalFont API",
        description="Converts photographed handwriting template pages into a personalized TTF/OTF font.",
        version="1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(templates_router)
    app.include_router(jobs_router)
    app.include_router(character_set_router)

    @app.get("/api/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
