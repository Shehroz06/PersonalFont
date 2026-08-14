from __future__ import annotations

from pydantic import BaseModel


class GeneratedFont(BaseModel):
    family_name: str
    version: str
    glyph_count: int
    ttf_path: str
    otf_path: str
