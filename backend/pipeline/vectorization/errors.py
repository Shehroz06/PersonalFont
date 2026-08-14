"""Explicit, actionable exceptions for the vectorization stage (spec §17)."""

from __future__ import annotations


class VectorizationError(Exception):
    """Raised when a glyph bitmap cannot be traced into vector paths."""
