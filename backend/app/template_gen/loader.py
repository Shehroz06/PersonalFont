"""Loads a generated template_v*.json back into a TemplateDocument, so
alignment (and later segmentation, and the API) read the same schema that
generate.py writes, instead of re-parsing raw JSON themselves.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.template_gen.schema import TemplateDocument

_TEMPLATE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


def is_valid_template_id(template_id: str) -> bool:
    """Whether ``template_id`` is safe to join into a filesystem path
    (spec §18) — used by the API before resolving a template_id straight
    out of a request into ``templates_root / f"{template_id}.json"``."""
    return bool(_TEMPLATE_ID_PATTERN.match(template_id))


def load_template_document(json_path: Path) -> TemplateDocument:
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    return TemplateDocument.model_validate(data)
