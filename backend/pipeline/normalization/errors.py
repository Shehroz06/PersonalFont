"""Explicit, actionable exceptions for the normalization stage (spec §17)."""

from __future__ import annotations


class NormalizationError(Exception):
    """Raised when a glyph cannot be normalized (e.g. it has no ink)."""
