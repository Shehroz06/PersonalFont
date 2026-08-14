"""Stage 9 (spec §11): assemble every vectorized glyph into a complete
TTF and OTF font.

Kept separate from vectorization (Phase 8) per spec §10 — this module
only knows about SVG path data in, font files out; it doesn't trace
bitmaps itself.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib import TTFont

from pipeline.font_generation.config import FontGenerationConfig, FontMetadata
from pipeline.font_generation.errors import FontGenerationError
from pipeline.font_generation.glyph_outline import (
    build_cff_charstring,
    build_notdef_cff_charstring,
    build_notdef_tt_glyph,
    build_tt_glyph,
    compute_advance_and_transform,
)
from pipeline.font_generation.schema import GeneratedFont
from pipeline.vectorization.schema import VectorizedGlyph

NOTDEF_GLYPH_NAME = ".notdef"
_SVG_NS = "{http://www.w3.org/2000/svg}"


def _read_svg_path_data(svg_path: str) -> str:
    try:
        root = ET.parse(svg_path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise FontGenerationError(f"Could not read/parse SVG at {svg_path!r}: {exc}") from exc

    path_element = root.find(f"{_SVG_NS}path")
    if path_element is None or "d" not in path_element.attrib:
        raise FontGenerationError(f"No <path> element found in {svg_path!r}.")
    return path_element.attrib["d"]


def _build_one_format(
    glyphs: list[VectorizedGlyph],
    metadata: FontMetadata,
    config: FontGenerationConfig,
    is_ttf: bool,
) -> TTFont:
    glyph_order = [NOTDEF_GLYPH_NAME]
    cmap: dict[int, str] = {}
    outlines: dict[str, object] = {
        NOTDEF_GLYPH_NAME: build_notdef_tt_glyph(config) if is_ttf else build_notdef_cff_charstring(config)
    }
    metrics: dict[str, tuple[int, int]] = {
        NOTDEF_GLYPH_NAME: (config.units_per_em, round(config.notdef_margin_units))
    }

    for glyph in glyphs:
        path_data = _read_svg_path_data(glyph.svg_path)
        transform, advance_width, left_bearing = compute_advance_and_transform(path_data, config)
        outline = (
            build_tt_glyph(path_data, transform)
            if is_ttf
            else build_cff_charstring(path_data, transform, advance_width)
        )

        glyph_order.append(glyph.character_id)
        cmap[ord(glyph.character)] = glyph.character_id
        outlines[glyph.character_id] = outline
        metrics[glyph.character_id] = (advance_width, round(left_bearing))

    builder = FontBuilder(config.units_per_em, isTTF=is_ttf)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(cmap)
    if is_ttf:
        builder.setupGlyf(outlines)
    else:
        builder.setupCFF(metadata.postscript_name, {}, outlines, {})
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=config.ascender, descent=config.descender)
    builder.setupNameTable(
        {
            "familyName": metadata.family_name,
            "styleName": metadata.style_name,
            "uniqueFontIdentifier": f"{metadata.postscript_name};{metadata.version}",
            "fullName": metadata.full_name,
            "psName": metadata.postscript_name,
            "version": metadata.version,
            "description": metadata.description,
            "manufacturer": metadata.creator,
        }
    )
    builder.setupOS2(
        sTypoAscender=config.ascender,
        sTypoDescender=config.descender,
        usWinAscent=config.ascender,
        usWinDescent=abs(config.descender),
    )
    builder.setupPost()
    return builder.font


def generate_fonts(
    glyphs: list[VectorizedGlyph],
    output_dir: Path,
    metadata: FontMetadata | None = None,
    config: FontGenerationConfig | None = None,
) -> GeneratedFont:
    """Build a TTF and an OTF from ``glyphs`` and save them under
    ``output_dir``. Every glyph must have valid Unicode-mappable
    ``character`` and a unique ``character_id`` (used as the font glyph
    name) — both already guaranteed by app.template_gen.character_set.
    """
    if not glyphs:
        raise FontGenerationError("Cannot generate a font with zero glyphs.")

    metadata = metadata or FontMetadata()
    config = config or FontGenerationConfig()
    output_dir.mkdir(parents=True, exist_ok=True)

    ttf_font = _build_one_format(glyphs, metadata, config, is_ttf=True)
    otf_font = _build_one_format(glyphs, metadata, config, is_ttf=False)

    ttf_path = output_dir / f"{metadata.postscript_name}.ttf"
    otf_path = output_dir / f"{metadata.postscript_name}.otf"
    ttf_font.save(str(ttf_path))
    otf_font.save(str(otf_path))

    return GeneratedFont(
        family_name=metadata.family_name,
        version=metadata.version,
        glyph_count=len(glyphs),
        ttf_path=str(ttf_path),
        otf_path=str(otf_path),
    )
