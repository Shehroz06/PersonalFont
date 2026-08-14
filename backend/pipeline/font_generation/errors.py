"""Explicit, actionable exceptions for the font generation stage (spec §17)."""

from __future__ import annotations


class FontGenerationError(Exception):
    """Raised when a font cannot be built from the given glyphs."""
