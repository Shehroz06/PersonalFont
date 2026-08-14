"""Top-level entry point that ties layout + schema + PDF rendering together
to produce a versioned template (PDF + JSON pair) under templates/.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.template_gen.layout import LayoutConfig, compute_layout
from app.template_gen.pdf_renderer import render_template_pdf
from app.template_gen.schema import TemplateDocument, build_template_document

TEMPLATE_VERSION = "1.0"
TEMPLATE_ID = "template_v1"


def generate_template(
    output_dir: Path,
    template_id: str = TEMPLATE_ID,
    template_version: str = TEMPLATE_VERSION,
    config: LayoutConfig | None = None,
) -> tuple[Path, Path, TemplateDocument]:
    """Generate the PDF and JSON for one template version.

    Returns (pdf_path, json_path, document) so callers (CLI, tests) can
    inspect the result without re-parsing the JSON off disk.
    """
    config = config or LayoutConfig()
    output_dir.mkdir(parents=True, exist_ok=True)

    page_layouts = compute_layout(config=config)
    document = build_template_document(
        template_id=template_id,
        template_version=template_version,
        page_layouts=page_layouts,
        page_width=config.page_width,
        page_height=config.page_height,
    )

    pdf_path = output_dir / f"{template_id}.pdf"
    json_path = output_dir / f"{template_id}.json"

    render_template_pdf(page_layouts, str(pdf_path), config, template_id)
    json_path.write_text(json.dumps(document.model_dump(), indent=2), encoding="utf-8")

    return pdf_path, json_path, document
