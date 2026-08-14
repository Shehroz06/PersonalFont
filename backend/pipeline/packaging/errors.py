"""Explicit, actionable exceptions for the packaging stage (spec §17)."""

from __future__ import annotations


class PackagingError(Exception):
    """Raised when the downloadable font package cannot be assembled."""
