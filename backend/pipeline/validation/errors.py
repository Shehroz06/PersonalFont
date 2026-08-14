"""Internal-only exception for the validation stage.

Never escapes validate_glyphs() — per spec §8/§16, one glyph failing to
even load must not fail the batch, so the batch orchestrator catches this
and converts it into an invalid ValidationResult instead of raising.
"""

from __future__ import annotations


class ValidationError(Exception):
    pass
