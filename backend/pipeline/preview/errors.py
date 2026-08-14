"""Explicit, actionable exceptions for the preview stage (spec §17)."""

from __future__ import annotations


class PreviewError(Exception):
    """Raised when a font preview (image or PDF) cannot be rendered."""
