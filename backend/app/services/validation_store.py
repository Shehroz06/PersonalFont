"""Persists a completed job's per-character validation results to
jobs/{job_id}/validation.json, so GET /api/jobs/{id}/validation can serve
them without keeping anything about the job in memory between requests
(the background task that ran the pipeline and the request that later
reads the results may not even be handled by the same process).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.services.jobs import JobPaths
from pipeline.validation.schema import ValidationResult

_VALIDATION_FILENAME = "validation.json"


def _validation_path(job_paths: JobPaths) -> Path:
    return job_paths.root / _VALIDATION_FILENAME


def write_validation_results(job_paths: JobPaths, validations: list[ValidationResult]) -> None:
    payload = [v.model_dump() for v in validations]
    _validation_path(job_paths).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_validation_results(job_paths: JobPaths) -> list[ValidationResult]:
    path = _validation_path(job_paths)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [ValidationResult.model_validate(item) for item in data]
