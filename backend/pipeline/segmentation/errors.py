"""Explicit, actionable exceptions for the segmentation stage (spec §17)."""

from __future__ import annotations


class SegmentationError(Exception):
    """Raised when a character's crop region cannot be extracted."""
