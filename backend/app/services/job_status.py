"""Disk-persisted job status, read/written as jobs/{job_id}/status.json.

Persisted to disk (not an in-memory dict) so status survives a server
restart and is correct regardless of how many worker processes are
running it — an in-memory store wouldn't be shared across uvicorn
workers, but every worker can read/write the same file. This matches
Project_spec.txt's V1 storage decision (local filesystem, no database).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.services.jobs import JobPaths

JobState = Literal["created", "uploading", "processing", "completed", "failed"]

_STATUS_FILENAME = "status.json"


class JobStatus(BaseModel):
    job_id: str
    state: JobState
    template_id: str
    pages_uploaded: int = 0
    valid_glyph_count: int | None = None
    invalid_glyph_count: int | None = None
    error: str | None = None
    created_at: float
    updated_at: float


def _status_path(job_paths: JobPaths) -> Path:
    return job_paths.root / _STATUS_FILENAME


def init_status(job_paths: JobPaths, job_id: str, template_id: str) -> JobStatus:
    now = time.time()
    status = JobStatus(job_id=job_id, state="created", template_id=template_id, created_at=now, updated_at=now)
    write_status(job_paths, status)
    return status


def read_status(job_paths: JobPaths) -> JobStatus | None:
    path = _status_path(job_paths)
    if not path.exists():
        return None
    return JobStatus.model_validate_json(path.read_text(encoding="utf-8"))


def write_status(job_paths: JobPaths, status: JobStatus) -> None:
    _status_path(job_paths).write_text(status.model_dump_json(indent=2), encoding="utf-8")


def update_status(job_paths: JobPaths, **changes: object) -> JobStatus:
    current = read_status(job_paths)
    if current is None:
        raise ValueError(f"Job status has not been initialized for {job_paths.root}.")

    data = current.model_dump()
    data.update(changes)
    data["updated_at"] = time.time()

    updated = JobStatus.model_validate(data)
    write_status(job_paths, updated)
    return updated
