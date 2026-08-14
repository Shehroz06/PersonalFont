import json
import zipfile
from pathlib import Path

import pytest

from pipeline.font_generation.build import generate_fonts
from pipeline.font_generation.config import FontMetadata
from pipeline.packaging.errors import PackagingError
from pipeline.packaging.package import build_font_package
from pipeline.preview.render import generate_preview_image, generate_preview_pdf
from pipeline.validation.schema import ValidationResult
from tests.font_generation_helpers import build_sample_glyphs


@pytest.fixture
def package_inputs(tmp_path: Path):
    svg_dir = tmp_path / "svg"
    glyphs = build_sample_glyphs(svg_dir)
    metadata = FontMetadata(family_name="My Handwriting", creator="Jane Doe", version="1.2")
    font = generate_fonts(glyphs, tmp_path / "font", metadata=metadata)

    preview_png = tmp_path / "preview" / "preview.png"
    preview_pdf = tmp_path / "preview" / "preview.pdf"
    generate_preview_image(Path(font.ttf_path), preview_png)
    generate_preview_pdf(Path(font.ttf_path), preview_pdf, metadata.family_name)

    validations = [
        ValidationResult(character="A", character_id="uppercase_A", valid=True, confidence=1.0, warnings=[]),
        ValidationResult(character="o", character_id="lowercase_o", valid=True, confidence=1.0, warnings=[]),
        ValidationResult(character="L", character_id="uppercase_L", valid=True, confidence=1.0, warnings=[]),
        ValidationResult(
            character="B",
            character_id="uppercase_B",
            valid=False,
            confidence=0.0,
            warnings=["Empty glyph"],
        ),
    ]

    return {
        "font": font,
        "metadata": metadata,
        "svg_dir": svg_dir,
        "preview_png": preview_png,
        "preview_pdf": preview_pdf,
        "validations": validations,
    }


def test_build_font_package_creates_zip_with_expected_members(tmp_path: Path, package_inputs: dict):
    output_dir = tmp_path / "package_out"

    package = build_font_package(
        generated_font=package_inputs["font"],
        metadata=package_inputs["metadata"],
        template_id="template_v1",
        validations=package_inputs["validations"],
        svg_dir=package_inputs["svg_dir"],
        preview_png_path=package_inputs["preview_png"],
        preview_pdf_path=package_inputs["preview_pdf"],
        output_dir=output_dir,
    )

    zip_path = Path(package.zip_path)
    assert zip_path.exists()
    assert zip_path.parent == output_dir
    assert zip_path.name == "MyHandwriting-Regular.zip"

    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        assert names == {
            "MyHandwriting-Regular.ttf",
            "MyHandwriting-Regular.otf",
            "preview.png",
            "preview.pdf",
            "glyphs.zip",
            "metadata.json",
            "README.txt",
        }


def test_build_font_package_metadata_json_contents(tmp_path: Path, package_inputs: dict):
    package = build_font_package(
        generated_font=package_inputs["font"],
        metadata=package_inputs["metadata"],
        template_id="template_v1",
        validations=package_inputs["validations"],
        svg_dir=package_inputs["svg_dir"],
        preview_png_path=package_inputs["preview_png"],
        preview_pdf_path=package_inputs["preview_pdf"],
        output_dir=tmp_path / "out",
    )

    with zipfile.ZipFile(package.zip_path) as zf:
        metadata = json.loads(zf.read("metadata.json"))

    assert metadata["family_name"] == "My Handwriting"
    assert metadata["creator"] == "Jane Doe"
    assert metadata["version"] == "1.2"
    assert metadata["template_id"] == "template_v1"
    assert metadata["glyph_count"] == package_inputs["font"].glyph_count
    assert set(metadata["valid_characters"]) == {"uppercase_A", "lowercase_o", "uppercase_L"}
    assert metadata["invalid_characters"] == ["uppercase_B"]
    assert "generated_at" in metadata


def test_build_font_package_readme_mentions_coverage(tmp_path: Path, package_inputs: dict):
    package = build_font_package(
        generated_font=package_inputs["font"],
        metadata=package_inputs["metadata"],
        template_id="template_v1",
        validations=package_inputs["validations"],
        svg_dir=package_inputs["svg_dir"],
        preview_png_path=package_inputs["preview_png"],
        preview_pdf_path=package_inputs["preview_pdf"],
        output_dir=tmp_path / "out",
    )

    with zipfile.ZipFile(package.zip_path) as zf:
        readme = zf.read("README.txt").decode("utf-8")

    assert "My Handwriting" in readme
    assert "3 of 4 requested characters" in readme
    assert "1 character(s) need a clearer rewrite" in readme


def test_build_font_package_glyphs_zip_contains_svgs(tmp_path: Path, package_inputs: dict):
    package = build_font_package(
        generated_font=package_inputs["font"],
        metadata=package_inputs["metadata"],
        template_id="template_v1",
        validations=package_inputs["validations"],
        svg_dir=package_inputs["svg_dir"],
        preview_png_path=package_inputs["preview_png"],
        preview_pdf_path=package_inputs["preview_pdf"],
        output_dir=tmp_path / "out",
    )

    with zipfile.ZipFile(package.zip_path) as outer_zf:
        glyphs_zip_bytes = outer_zf.read("glyphs.zip")

    import io

    with zipfile.ZipFile(io.BytesIO(glyphs_zip_bytes)) as inner_zf:
        names = set(inner_zf.namelist())
        assert names == {"uppercase_A.svg", "lowercase_o.svg", "uppercase_L.svg"}


def test_build_font_package_readme_says_all_included_when_no_invalid(tmp_path: Path, package_inputs: dict):
    all_valid = [
        ValidationResult(character="A", character_id="uppercase_A", valid=True, confidence=1.0, warnings=[]),
    ]

    package = build_font_package(
        generated_font=package_inputs["font"],
        metadata=package_inputs["metadata"],
        template_id="template_v1",
        validations=all_valid,
        svg_dir=package_inputs["svg_dir"],
        preview_png_path=package_inputs["preview_png"],
        preview_pdf_path=package_inputs["preview_pdf"],
        output_dir=tmp_path / "out",
    )

    with zipfile.ZipFile(package.zip_path) as zf:
        readme = zf.read("README.txt").decode("utf-8")

    assert "Every requested character was included." in readme


def test_build_font_package_raises_when_preview_missing(tmp_path: Path, package_inputs: dict):
    with pytest.raises(PackagingError):
        build_font_package(
            generated_font=package_inputs["font"],
            metadata=package_inputs["metadata"],
            template_id="template_v1",
            validations=package_inputs["validations"],
            svg_dir=package_inputs["svg_dir"],
            preview_png_path=tmp_path / "missing.png",
            preview_pdf_path=package_inputs["preview_pdf"],
            output_dir=tmp_path / "out",
        )
