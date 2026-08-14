"""App-wide settings, read from environment variables with sensible
local-filesystem defaults (Project_spec.txt: V1 storage is local
filesystem, no database/S3). Plain env-var reads rather than a
pydantic-settings dependency — the surface here is small enough not to
need it (dev rule: avoid unnecessary dependencies).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass(frozen=True)
class Settings:
    jobs_root: Path = Path(os.environ.get("PERSONALFONT_JOBS_ROOT", str(REPO_ROOT / "jobs")))
    templates_root: Path = Path(os.environ.get("PERSONALFONT_TEMPLATES_ROOT", str(REPO_ROOT / "templates")))
    # Next.js dev falls back to 3001 (then 3002, ...) whenever 3000 is
    # already taken by something else on the machine — observed directly
    # while manually testing Phase 12, where an unrelated dev server
    # already held 3000. Defaulting to just one port silently breaks the
    # frontend with an opaque CORS error the moment that happens.
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.environ.get(
            "PERSONALFONT_CORS_ORIGINS", "http://localhost:3000,http://localhost:3001"
        ).split(",")
        if origin.strip()
    )


def get_settings() -> Settings:
    return Settings()
