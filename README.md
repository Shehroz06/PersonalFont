# PersonalFont

A handwriting-to-font system that converts a user's handwritten template pages into a personalized installable font (TTF/OTF).

V1 is a deterministic pipeline — no generative AI, no model training. See `Initial_project_prompt.txt`, `Project_spec.txt`, `Functional_requirements.txt`, and `Non_Functional_requirements` for the full specification this build follows.

## Status

Phase 1 (scaffolding) and Phase 2 (template generation) are implemented. See `docs/architecture.md` for the full development order and current progress.

## Repository layout

```
backend/
  app/
    template_gen/   # template layout, JSON schema, PDF rendering (Phase 2)
    api/             # FastAPI routes (Phase 11)
    models/          # Pydantic request/response models
    services/        # job orchestration
  pipeline/
    preprocessing/ alignment/ segmentation/ validation/
    normalization/ vectorization/ font_generation/ preview/ packaging/
  tests/
  requirements.txt
frontend/            # Next.js app (Phase 12)
templates/           # generated template_v1.pdf / template_v1.json
jobs/                # per-job working directories (gitignored)
output/              # generated font packages (gitignored)
docs/
scripts/
```

## Setup

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Generate the handwriting template

```bash
backend/.venv/bin/python scripts/generate_template.py
```

Produces `templates/template_v1.pdf` (print this and hand-write the characters) and `templates/template_v1.json` (the data-driven description of every character box and alignment marker the pipeline will read — never hardcode template coordinates elsewhere).

## Run tests

```bash
cd backend
.venv/bin/python -m pytest -q
```
