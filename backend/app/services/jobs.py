"""Per-job directory layout (spec §15) and safe job-id handling.

Every font generation request gets an isolated directory under a jobs
root:

    jobs/{job_id}/uploads/
    jobs/{job_id}/processed/
    jobs/{job_id}/glyphs/
    jobs/{job_id}/svg/
    jobs/{job_id}/font/
    jobs/{job_id}/preview/
    jobs/{job_id}/logs/

job_id must never be trusted as a raw path component (spec §18) — a
crafted id like "../../etc" must not be able to escape the jobs root. All
job ids this system creates are uuid4 hex, and resolve_job_paths rejects
anything else.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

_JOB_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")

_SUBDIRS = ("uploads", "processed", "glyphs", "svg", "font", "preview", "logs")


def generate_job_id() -> str:
    return uuid.uuid4().hex


def is_valid_job_id(job_id: str) -> bool:
    return bool(_JOB_ID_PATTERN.match(job_id))


@dataclass(frozen=True)
class JobPaths:
    root: Path

    @property
    def uploads(self) -> Path:
        return self.root / "uploads"

    @property
    def processed(self) -> Path:
        return self.root / "processed"

    @property
    def glyphs(self) -> Path:
        return self.root / "glyphs"

    @property
    def svg(self) -> Path:
        return self.root / "svg"

    @property
    def font(self) -> Path:
        return self.root / "font"

    @property
    def preview(self) -> Path:
        return self.root / "preview"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    def ensure_dirs(self) -> None:
        for name in _SUBDIRS:
            (self.root / name).mkdir(parents=True, exist_ok=True)


def resolve_job_paths(jobs_root: Path, job_id: str) -> JobPaths:
    """Resolve ``job_id``'s directory under ``jobs_root``.

    Raises ValueError for anything that isn't a well-formed job id,
    rather than silently joining an attacker-controlled path.
    """
    if not is_valid_job_id(job_id):
        raise ValueError(f"Invalid job id: {job_id!r}")
    return JobPaths(root=jobs_root / job_id)
