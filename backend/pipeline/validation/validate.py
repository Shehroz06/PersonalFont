"""Stage 6 (spec §8): score each extracted glyph for usability without
ever failing the job over one bad character (spec §8/§16/NFR-06).

validate_glyph scores a single in-memory crop. validate_glyphs is the
batch entry point real callers use — it reads each glyph's saved PNG and
guarantees one glyph's failure (even a corrupt/unreadable file) becomes an
invalid ValidationResult, not an exception that takes down the batch.
"""

from __future__ import annotations

import cv2
import numpy as np

from pipeline.segmentation.schema import ExtractedGlyph
from pipeline.validation.config import ValidationConfig
from pipeline.validation.errors import ValidationError
from pipeline.validation.rules import (
    check_component_count,
    check_foreground_ratio,
    check_glyph_size,
    check_touches_boundary,
    ink_pixel_count,
)
from pipeline.validation.schema import ValidationResult


def validate_glyph(
    image: np.ndarray,
    character: str,
    character_id: str,
    config: ValidationConfig | None = None,
) -> ValidationResult:
    config = config or ValidationConfig()

    if ink_pixel_count(image) == 0:
        return ValidationResult(
            character=character,
            character_id=character_id,
            valid=False,
            confidence=0.0,
            warnings=["Empty glyph: no handwriting was detected in this box"],
        )

    checks = [
        check_foreground_ratio(image, config),
        check_glyph_size(image, config),
        check_touches_boundary(image, config),
        check_component_count(image, character),
    ]

    warnings = [
        warning for score, warning in checks if warning is not None and score < config.warning_score_threshold
    ]
    confidence = 1.0
    for score, _warning in checks:
        confidence *= score
    confidence = round(confidence, 4)

    valid = confidence >= config.min_confidence and not warnings
    if not valid and not warnings:
        # Defensive: keep the invariant that an invalid glyph always
        # explains itself, even if every individual check scored above
        # its own warning threshold but the combined confidence still
        # fell short.
        warnings = [f"Overall confidence too low ({confidence:.2f})"]

    return ValidationResult(
        character=character,
        character_id=character_id,
        valid=valid,
        confidence=confidence,
        warnings=warnings,
    )


def validate_glyphs(
    glyphs: list[ExtractedGlyph],
    config: ValidationConfig | None = None,
) -> list[ValidationResult]:
    config = config or ValidationConfig()
    results: list[ValidationResult] = []

    for glyph in glyphs:
        try:
            image = cv2.imread(glyph.image_path, cv2.IMREAD_GRAYSCALE)
            if image is None:
                raise ValidationError(f"Could not read glyph image at {glyph.image_path}")
            result = validate_glyph(image, glyph.character, glyph.character_id, config)
        except Exception as exc:  # noqa: BLE001 - deliberately broad: one glyph must never sink the batch
            result = ValidationResult(
                character=glyph.character,
                character_id=glyph.character_id,
                valid=False,
                confidence=0.0,
                warnings=[f"Validation failed unexpectedly: {exc}"],
            )
        results.append(result)

    return results
