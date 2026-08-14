"""Structured, per-job logging (spec NFR-10): every pipeline stage emits
one JSON-lines record per event to jobs/{job_id}/logs/pipeline.log, using
the event names NFR-10 specifies (JOB_CREATED, PAGE_PREPROCESSED,
PAGE_ALIGNED, GLYPHS_EXTRACTED, VALIDATION_COMPLETED, FONT_GENERATED,
JOB_COMPLETED) plus a couple this pipeline also needs (PAGE_FAILED,
JOB_FAILED, DUPLICATE_GLYPH_DISCARDED) to keep failures just as
observable as successes.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path


def get_job_logger(job_id: str, log_dir: Path) -> logging.Logger:
    """A logger dedicated to one job, writing JSON-lines to
    ``log_dir/pipeline.log``. Idempotent per job_id — calling this again
    for the same job_id returns the same logger without adding a
    duplicate handler.
    """
    logger = logging.getLogger(f"personalfont.job.{job_id}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_dir / "pipeline.log")
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    return logger


def log_event(logger: logging.Logger, event: str, **fields) -> None:
    record = {"event": event, "timestamp": time.time(), **fields}
    logger.info(json.dumps(record))
