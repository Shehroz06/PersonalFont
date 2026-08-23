from pathlib import Path

from reportlab.pdfbase.pdfmetrics import stringWidth

from app.template_gen.character_set import get_character_set
from app.template_gen.layout import LayoutConfig, MARKER_CORNERS, compute_layout
from app.template_gen.generate import generate_template
from app.template_gen.pdf_renderer import _CAPTION_FONT_SIZE, _caption_for
from app.template_gen.schema import build_template_document


def test_character_set_has_no_duplicate_ids():
    chars = get_character_set()
    ids = [c.character_id for c in chars]
    assert len(ids) == len(set(ids))


def test_character_set_covers_required_categories():
    chars = get_character_set()
    categories = {c.category for c in chars}
    assert categories == {"uppercase", "lowercase", "digit", "punctuation"}
    assert sum(c.category == "uppercase" for c in chars) == 26
    assert sum(c.category == "lowercase" for c in chars) == 26
    assert sum(c.category == "digit" for c in chars) == 10


def test_compute_layout_places_every_character_exactly_once():
    chars = get_character_set()
    pages = compute_layout()

    all_ids = [el.character_id for page in pages for el in page.elements]
    assert len(all_ids) == len(chars)
    assert set(all_ids) == {c.character_id for c in chars}


def test_compute_layout_respects_cells_per_page():
    config = LayoutConfig()
    pages = compute_layout(config=config)

    for page in pages[:-1]:
        assert len(page.elements) == config.cells_per_page
    assert len(pages[-1].elements) <= config.cells_per_page


def test_element_boxes_stay_within_page_bounds():
    config = LayoutConfig()
    pages = compute_layout(config=config)

    for page in pages:
        for el in page.elements:
            assert el.x >= 0
            assert el.y >= 0
            assert el.x + el.width <= config.page_width
            assert el.y + el.height <= config.page_height


def test_element_boxes_do_not_overlap_each_other():
    pages = compute_layout()

    for page in pages:
        boxes = [(el.x, el.y, el.x + el.width, el.y + el.height) for el in page.elements]
        for i, a in enumerate(boxes):
            for b in boxes[i + 1 :]:
                overlap_x = a[0] < b[2] and b[0] < a[2]
                overlap_y = a[1] < b[3] and b[1] < a[3]
                assert not (overlap_x and overlap_y), "character boxes overlap"


def test_every_page_has_four_markers_with_unique_ids():
    pages = compute_layout()
    seen_ids = set()

    for page in pages:
        assert len(page.markers) == len(MARKER_CORNERS)
        corners = {m.corner for m in page.markers}
        assert corners == set(MARKER_CORNERS)
        for m in page.markers:
            assert m.marker_id not in seen_ids
            seen_ids.add(m.marker_id)


def test_markers_do_not_overlap_character_grid():
    config = LayoutConfig()
    pages = compute_layout(config=config)

    for page in pages:
        marker_boxes = [(m.x, m.y, m.x + m.size, m.y + m.size) for m in page.markers]
        for el in page.elements:
            el_box = (el.x, el.y, el.x + el.width, el.y + el.height)
            for mb in marker_boxes:
                overlap_x = el_box[0] < mb[2] and mb[0] < el_box[2]
                overlap_y = el_box[1] < mb[3] and mb[1] < el_box[3]
                assert not (overlap_x and overlap_y), "marker overlaps a character box"


def test_build_template_document_matches_layout():
    config = LayoutConfig()
    pages = compute_layout(config=config)
    doc = build_template_document(
        template_id="template_v1",
        template_version="1.0",
        page_layouts=pages,
        page_width=config.page_width,
        page_height=config.page_height,
    )

    assert doc.character_count == sum(len(p.elements) for p in pages)
    assert len(doc.pages) == len(pages)
    assert doc.pages[0].elements[0].unicode == "U+0041"  # 'A'


def test_generate_template_writes_pdf_and_json(tmp_path: Path):
    pdf_path, json_path, document = generate_template(tmp_path)

    assert pdf_path.exists()
    assert json_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF-")

    import json as json_module

    on_disk = json_module.loads(json_path.read_text())
    assert on_disk["template_id"] == "template_v1"
    assert on_disk["character_count"] == document.character_count


def test_caption_for_strips_punctuation_prefix():
    assert _caption_for("punctuation_bracket_close") == "bracket_close"
    assert _caption_for("punctuation_period") == "period"


def test_caption_for_leaves_non_punctuation_ids_unchanged():
    assert _caption_for("uppercase_A") == "uppercase_A"
    assert _caption_for("lowercase_a") == "lowercase_a"
    assert _caption_for("digit_0") == "digit_0"


def test_every_caption_fits_within_the_box_width():
    # Regression test: the caption below each box is the *only* thing
    # identifying which character goes there (no guide glyph is drawn
    # inside the box — see pdf_renderer.py). A caption wider than its own
    # box overlaps its neighbors' captions and becomes illegible, which
    # is exactly what happened with the raw character_id before
    # _caption_for existed: several punctuation ids (up to ~71pt, e.g.
    # "punctuation_bracket_close") didn't fit a 52pt-wide box.
    config = LayoutConfig()
    for spec in get_character_set():
        caption = _caption_for(spec.character_id)
        width = stringWidth(caption, "Helvetica", _CAPTION_FONT_SIZE)
        assert width <= config.cell_width, f"{spec.character_id!r} caption {caption!r} ({width:.1f}pt) overflows"
