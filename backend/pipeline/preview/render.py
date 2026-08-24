"""Stage 12 (spec §12): render a preview of the generated font — a PNG
image and a print-friendly PDF, both showing the same sample lines
rendered with the real font, not a mock.

Kept separate from font generation (Phase 9) and packaging (this
directory's sibling) — this module only turns a font file into preview
media, nothing else.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont as ReportLabTTFont
from reportlab.pdfgen import canvas as pdf_canvas

from pipeline.preview.config import PreviewConfig
from pipeline.preview.errors import PreviewError


def generate_preview_image(ttf_path: Path, output_path: Path, config: PreviewConfig | None = None) -> Path:
    """Render config.sample_lines with the real font to a PNG. Characters
    absent from the font (e.g. one that failed validation) render as
    whatever the font's own .notdef glyph looks like — an honest gap,
    not hidden or substituted."""
    config = config or PreviewConfig()

    try:
        font = ImageFont.truetype(str(ttf_path), config.font_size)
    except OSError as exc:
        raise PreviewError(f"Could not load font at {ttf_path!r} for preview rendering: {exc}") from exc

    image = Image.new("RGB", (config.image_width, config.image_height), "white")
    draw = ImageDraw.Draw(image)

    y = config.margin
    for line in config.sample_lines:
        draw.text((config.margin, y), line, font=font, fill="black")
        y += config.line_spacing

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def generate_preview_pdf(
    ttf_path: Path,
    output_path: Path,
    family_name: str,
    config: PreviewConfig | None = None,
) -> Path:
    config = config or PreviewConfig()

    # A fresh id per call, not a fixed name — reportlab's font registry is
    # process-global, and a long-lived server process (the API's
    # background tasks) will call this for many different jobs/fonts.
    font_id = f"preview-{uuid.uuid4().hex}"
    try:
        pdfmetrics.registerFont(ReportLabTTFont(font_id, str(ttf_path)))
    except Exception as exc:
        raise PreviewError(f"Could not load font at {ttf_path!r} for PDF preview: {exc}") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = pdf_canvas.Canvas(str(output_path), pagesize=LETTER)
    _page_width, page_height = LETTER

    c.setFont("Helvetica-Bold", 16)
    c.drawString(config.margin, page_height - config.margin - 10, f"{family_name} Preview")

    pdf_font_size = config.font_size * 0.6
    pdf_line_spacing = config.line_spacing * 0.6
    y = page_height - config.margin - 60
    c.setFont(font_id, pdf_font_size)
    for line in config.sample_lines:
        c.drawString(config.margin, y, line)
        y -= pdf_line_spacing

    c.save()
    return output_path
