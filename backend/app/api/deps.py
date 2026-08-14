"""Shared FastAPI dependencies: resolving configured roots and turning a
path-unsafe/nonexistent job_id into a proper 404 instead of a raised
ValueError leaking out of a route.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, HTTPException

from app.config import get_settings
from app.services.jobs import JobPaths, resolve_job_paths


def get_jobs_root() -> Path:
    return get_settings().jobs_root


def get_templates_root() -> Path:
    return get_settings().templates_root


def get_job_paths(job_id: str, jobs_root: Path = Depends(get_jobs_root)) -> JobPaths:
    # jobs_root is itself a dependency (rather than called directly) so
    # tests can override get_jobs_root and have this respect it.
    try:
        job_paths = resolve_job_paths(jobs_root, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found.") from exc

    if not job_paths.root.is_dir():
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found.")
    return job_paths
