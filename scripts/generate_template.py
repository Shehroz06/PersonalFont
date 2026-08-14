#!/usr/bin/env python3
"""CLI: generate the versioned template PDF + JSON into templates/.

Usage:
    backend/.venv/bin/python scripts/generate_template.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.template_gen.generate import generate_template  # noqa: E402


def main() -> None:
    output_dir = REPO_ROOT / "templates"
    pdf_path, json_path, document = generate_template(output_dir)

    print(f"Generated {pdf_path}")
    print(f"Generated {json_path}")
    print(f"Pages: {len(document.pages)}  Characters: {document.character_count}")


if __name__ == "__main__":
    main()
