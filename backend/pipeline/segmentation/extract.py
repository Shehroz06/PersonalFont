"""Stage 5 (spec §7): crop each character's glyph out of an aligned page
image using the template's coordinates, and save it into the job's glyphs
directory.

Each crop also gets small connected components removed (see
pipeline.ink_geometry.remove_small_components) before saving — cleans up
scan/compression noise speckle at the source, so every downstream
consumer of the saved PNG (validation, normalization, the packaged
glyphs.zip) sees the same clean signal rather than each having to
re-derive it.

Filenames use each element's template character_id (e.g. "uppercase_A.png",
"punctuation_colon.png") rather than the raw character. The spec's example
("A.png") is illustrative — a literal character can't safely be a filename
for every entry in this character set: several punctuation marks
(`"`, `:`, `?`) are invalid in Windows paths, and 'A.png'/'a.png' collide
on case-insensitive filesystems (macOS, Windows). character_id is already
the template's stable, unique, filesystem-safe identifier for each glyph
(see app.template_gen.character_set), so reusing it here avoids inventing
a second naming scheme.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.template_gen.coordinates import element_box_px
from app.template_gen.schema import TemplatePage
from pipeline.ink_geometry import remove_small_components
from pipeline.segmentation.config import SegmentationConfig
from pipeline.segmentation.errors import SegmentationError
from pipeline.segmentation.schema import ExtractedGlyph, GlyphCropBox


def extract_glyphs(
    image: np.ndarray,
    page: TemplatePage,
    page_height_pt: float,
    dpi: float,
    job_id: str,
    output_dir: Path,
    source_image: str,
    extraction_confidence: float,
    config: SegmentationConfig | None = None,
) -> list[ExtractedGlyph]:
    """Crop every character box on ``page`` out of ``image`` (already
    aligned to template pixel space, e.g. AlignmentResult.aligned_image)
    and save each as its own PNG under ``output_dir``.

    ``extraction_confidence`` reflects how much to trust the crop's
    *location* — in practice, the alignment confidence that produced
    ``image`` — not the glyph's content quality, which Phase 6 validation
    assesses separately. A failed crop for one character raises
    SegmentationError rather than silently skipping it (spec §16: never
    silently discard a failed glyph) — the caller decides whether to let
    one bad glyph fail the whole page or catch it and continue.
    """
    config = config or SegmentationConfig()
    output_dir.mkdir(parents=True, exist_ok=True)

    image_height, image_width = image.shape[:2]
    results: list[ExtractedGlyph] = []

    for element in page.elements:
        x_px, y_px, w_px, h_px = element_box_px(element, page_height_pt, dpi)

        x0 = max(0, int(round(x_px)) - config.padding_px)
        y0 = max(0, int(round(y_px)) - config.padding_px)
        x1 = min(image_width, int(round(x_px + w_px)) + config.padding_px)
        y1 = min(image_height, int(round(y_px + h_px)) + config.padding_px)

        if x1 <= x0 or y1 <= y0:
            raise SegmentationError(
                f"Character '{element.character}' ({element.id}) on page {page.page} has an "
                "invalid crop region after alignment — it falls outside the aligned image "
                "entirely. This usually means the page did not align correctly; please "
                "re-upload a clearer photo of this page."
            )

        crop = image[y0:y1, x0:x1]
        crop = remove_small_components(crop, config.min_component_area_ratio)

        image_path = output_dir / f"{element.id}.png"
        cv2.imwrite(str(image_path), crop)

        results.append(
            ExtractedGlyph(
                job_id=job_id,
                page=page.page,
                character=element.character,
                character_id=element.id,
                source_image=source_image,
                crop_box=GlyphCropBox(x=x0, y=y0, width=x1 - x0, height=y1 - y0),
                extraction_confidence=extraction_confidence,
                image_path=str(image_path),
            )
        )

    return results
