"""Loads a generated template_v*.json back into a TemplateDocument, so
alignment (and later segmentation, and the API) read the same schema that
generate.py writes, instead of re-parsing raw JSON themselves.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.template_gen.schema import TemplateDocument


def load_template_document(json_path: Path) -> TemplateDocument:
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    return TemplateDocument.model_validate(data)
