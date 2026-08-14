"""Machine-readable per-glyph validation result (spec §8)."""

from __future__ import annotations

from pydantic import BaseModel


class ValidationResult(BaseModel):
    character: str
    character_id: str
    valid: bool
    confidence: float
    warnings: list[str]
