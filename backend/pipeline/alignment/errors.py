"""Explicit, actionable exceptions for the alignment stage (spec §17)."""

from __future__ import annotations


class AlignmentError(Exception):
    """Raised when a page cannot be reliably aligned to a template."""
