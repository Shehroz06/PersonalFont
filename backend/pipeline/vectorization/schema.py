from __future__ import annotations

from pydantic import BaseModel


class VectorizedGlyph(BaseModel):
    character: str
    character_id: str
    svg_path: str
