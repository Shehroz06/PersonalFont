"""Explicit, actionable exceptions for the preprocessing stage.

Per the project spec (§17), failures must say what went wrong and what the
user should do about it — never a bare "processing failed".
"""

from __future__ import annotations


class PreprocessingError(Exception):
    """Base class for all preprocessing-stage failures."""


class PageDetectionError(PreprocessingError):
    """Raised when no page-sized quadrilateral can be found in the image."""


class DeskewError(PreprocessingError):
    """Raised when a skew angle cannot be reliably estimated."""
