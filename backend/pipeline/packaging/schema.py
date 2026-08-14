from __future__ import annotations

from pydantic import BaseModel


class FontPackage(BaseModel):
    zip_path: str
