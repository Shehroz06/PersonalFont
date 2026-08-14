"""Stage 7 (spec §9/FR-07): crop each valid glyph to its content, scale it
(preserving aspect ratio) and place it on a fixed-size canvas aligned to a
shared baseline, so every glyph in the font sits consistently relative to
the others rather than each floating at its own crop's size and position.

Expects the ink=255/background=0 convention (pipeline.preprocessing.
thresholding) and outputs an image in the same convention, so
vectorization (Phase 8) can consume it directly.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.template_gen.character_set import character_set_by_id, is_descender, is_tall_glyph
from pipeline.ink_geometry import ink_bounding_box
from pipeline.normalization.config import NormalizationConfig
from pipeline.normalization.errors import NormalizationError
from pipeline.normalization.schema import NormalizedGlyph
from pipeline.segmentation.schema import ExtractedGlyph
from pipeline.validation.schema import ValidationResult


def normalize_glyph(
    image: np.ndarray,
    character: str,
    category: str,
    config: NormalizationConfig | None = None,
) -> np.ndarray:
    """Return a new canvas_height x canvas_width binary image containing
    ``image``'s ink, cropped to content, uniformly scaled to fit its
    height class (tall/short, plus a descender allowance if applicable),
    horizontally centered, and vertically placed against the shared
    baseline.

    Raises NormalizationError for an empty glyph — validation (Phase 6)
    is expected to have already screened those out; this is a defensive
    guard, not the primary place that decision gets made.
    """
    config = config or NormalizationConfig()

    bbox = ink_bounding_box(image)
    if bbox is None:
        raise NormalizationError(f"Cannot normalize glyph {character!r}: it has no ink content.")

    x0, y0, x1, y1 = bbox
    content = image[y0:y1, x0:x1]
    content_h, content_w = content.shape[:2]

    tall = is_tall_glyph(character, category)
    descender = is_descender(character)

    main_height_px = (config.tall_height_ratio if tall else config.short_height_ratio) * config.canvas_height
    descender_px = config.descender_ratio * config.canvas_height if descender else 0.0
    target_height_px = main_height_px + descender_px

    max_width_px = config.canvas_width * (1 - 2 * config.horizontal_margin_ratio)

    # Fit within (target_height_px, max_width_px) without distorting the
    # glyph's proportions — scale is bounded by whichever dimension is
    # tighter.
    scale = min(target_height_px / content_h, max_width_px / content_w)

    new_w = max(1, round(content_w * scale))
    new_h = max(1, round(content_h * scale))
    interpolation = cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA
    resized = cv2.resize(content, (new_w, new_h), interpolation=interpolation)
    # Interpolation introduces gray values; re-binarize to keep the
    # ink=255/background=0 convention strict for vectorization.
    _, resized = cv2.threshold(resized, 127, 255, cv2.THRESH_BINARY)

    baseline_y = round(config.baseline_ratio * config.canvas_height)
    bottom_y = baseline_y + round(descender_px)
    top_y = bottom_y - new_h
    left_x = round((config.canvas_width - new_w) / 2)

    # Defensive clamp: rounding could theoretically push an edge case a
    # pixel outside the canvas.
    top_y = max(0, min(top_y, config.canvas_height - new_h))
    left_x = max(0, min(left_x, config.canvas_width - new_w))

    canvas = np.zeros((config.canvas_height, config.canvas_width), dtype=np.uint8)
    canvas[top_y : top_y + new_h, left_x : left_x + new_w] = resized
    return canvas


def normalize_glyphs(
    glyphs: list[ExtractedGlyph],
    validations: list[ValidationResult],
    output_dir: Path,
    config: NormalizationConfig | None = None,
) -> list[NormalizedGlyph]:
    """Normalize every glyph that Phase 6 validation marked valid, saving
    each to ``output_dir`` and returning its metadata.

    Glyphs that failed validation are silently excluded here — that's not
    the "never discard a failed glyph" violation spec §16 warns about,
    since Phase 6 already reported them (with warnings) as needing a
    rewrite; they simply don't advance to font generation. A failure
    *within* this stage (unreadable image, unrecognized character_id) is
    different — those raise NormalizationError, since by this point the
    glyph was already validated and an error here means something is
    wrong at a system level, not with the handwriting.
    """
    config = config or NormalizationConfig()
    output_dir.mkdir(parents=True, exist_ok=True)

    valid_ids = {v.character_id for v in validations if v.valid}
    spec_by_id = character_set_by_id()

    results: list[NormalizedGlyph] = []
    for glyph in glyphs:
        if glyph.character_id not in valid_ids:
            continue

        spec = spec_by_id.get(glyph.character_id)
        if spec is None:
            raise NormalizationError(
                f"Unknown character_id {glyph.character_id!r}: not part of the configured character set."
            )

        image = cv2.imread(glyph.image_path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise NormalizationError(f"Could not read glyph image at {glyph.image_path!r} for normalization.")

        normalized = normalize_glyph(image, glyph.character, spec.category, config)

        output_path = output_dir / f"{glyph.character_id}.png"
        cv2.imwrite(str(output_path), normalized)

        results.append(
            NormalizedGlyph(character=glyph.character, character_id=glyph.character_id, image_path=str(output_path))
        )

    return results
