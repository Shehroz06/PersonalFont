"""Machine-readable metadata for one extracted glyph (spec §7)."""

from __future__ import annotations

from pydantic import BaseModel


class GlyphCropBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class ExtractedGlyph(BaseModel):
    job_id: str
    page: int
    character: str
    character_id: str
    source_image: str
    crop_box: GlyphCropBox
    extraction_confidence: float
    image_path: str
