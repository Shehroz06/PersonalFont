from __future__ import annotations

from pydantic import BaseModel


class NormalizedGlyph(BaseModel):
    character: str
    character_id: str
    image_path: str
