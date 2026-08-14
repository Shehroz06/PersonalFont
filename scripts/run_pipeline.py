#!/usr/bin/env python3
"""CLI: run the full PersonalFont V1 pipeline end-to-end on uploaded page
photographs and produce a TTF/OTF font.

Usage:
    backend/.venv/bin/python scripts/run_pipeline.py page1.jpg page2.jpg \
        --font-name "My Handwriting" --creator "Jane Doe"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.jobs import generate_job_id, resolve_job_paths  # noqa: E402
from app.services.pipeline_runner import PipelineError, run_pipeline  # noqa: E402
from app.services.uploads import UploadValidationError, save_local_page_file  # noqa: E402
from app.template_gen.loader import load_template_document  # noqa: E402
from pipeline.font_generation.config import FontMetadata  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PersonalFont V1 pipeline on uploaded page photos.")
    parser.add_argument("pages", nargs="+", type=Path, help="Path(s) to photographed template page image(s).")
    parser.add_argument("--template", type=Path, default=REPO_ROOT / "templates" / "template_v1.json")
    parser.add_argument("--jobs-root", type=Path, default=REPO_ROOT / "jobs")
    parser.add_argument("--font-name", default="PersonalFont")
    parser.add_argument("--creator", default="PersonalFont")
    parser.add_argument("--version", default="1.0")
    args = parser.parse_args()

    for page_path in args.pages:
        if not page_path.exists():
            parser.error(f"Page image not found: {page_path}")
    if not args.template.exists():
        parser.error(f"Template JSON not found: {args.template}")

    document = load_template_document(args.template)
    job_id = generate_job_id()
    job_paths = resolve_job_paths(args.jobs_root, job_id)
    job_paths.ensure_dirs()
    metadata = FontMetadata(family_name=args.font_name, creator=args.creator, version=args.version)

    print(f"Job {job_id}")

    try:
        saved_pages = [save_local_page_file(page_path, job_paths.uploads) for page_path in args.pages]
    except UploadValidationError as exc:
        print(f"Upload failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(saved_pages)} page(s) against {document.template_id}...\n")

    try:
        result = run_pipeline(job_id, saved_pages, document, job_paths, font_metadata=metadata)
    except PipelineError as exc:
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        sys.exit(1)

    for page in result.pages:
        if page.succeeded:
            print(
                f"  {page.source_image}: aligned to page {page.template_page} "
                f"(confidence {page.alignment_confidence:.2f}), {page.glyphs_extracted} glyphs extracted"
            )
        else:
            print(f"  {page.source_image}: FAILED - {page.error}")

    valid = [v for v in result.validations if v.valid]
    invalid = [v for v in result.validations if not v.valid]
    print(f"\nValidation: {len(valid)} valid, {len(invalid)} invalid out of {len(result.validations)} characters")
    if invalid:
        print("  Characters needing a rewrite:")
        for v in invalid:
            print(f"    {v.character!r} ({v.character_id}): {', '.join(v.warnings)}")

    print(
        f"\nFont generated: {result.font.family_name} v{result.font.version} "
        f"({result.font.glyph_count} glyphs)"
    )
    print(f"  TTF: {result.font.ttf_path}")
    print(f"  OTF: {result.font.otf_path}")
    print(f"\nLogs: {result.log_path}")


if __name__ == "__main__":
    main()
