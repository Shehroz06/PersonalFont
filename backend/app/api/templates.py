from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_templates_root
from app.api.schemas import TemplateSummary
from app.template_gen.loader import is_valid_template_id, load_template_document
from app.template_gen.schema import TemplateDocument

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=list[TemplateSummary])
def list_templates(templates_root: Path = Depends(get_templates_root)) -> list[TemplateSummary]:
    summaries: list[TemplateSummary] = []
    for json_path in sorted(templates_root.glob("*.json")):
        try:
            document = load_template_document(json_path)
        except Exception:
            continue  # not a valid template document; skip rather than fail the whole listing
        summaries.append(
            TemplateSummary(
                template_id=document.template_id,
                template_version=document.template_version,
                page_count=len(document.pages),
                character_count=document.character_count,
            )
        )
    return summaries


@router.get("/{template_id}", response_model=TemplateDocument)
def get_template(template_id: str, templates_root: Path = Depends(get_templates_root)) -> TemplateDocument:
    if not is_valid_template_id(template_id):
        raise HTTPException(status_code=400, detail="Invalid template id.")

    json_path = templates_root / f"{template_id}.json"
    if not json_path.is_file():
        raise HTTPException(status_code=404, detail=f"Template {template_id!r} not found.")

    return load_template_document(json_path)
