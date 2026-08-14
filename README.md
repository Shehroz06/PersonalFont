# PersonalFont

A handwriting-to-font system that converts a user's handwritten template pages into a personalized installable font (TTF/OTF).

V1 is a deterministic pipeline — no generative AI, no model training. See `Initial_project_prompt.txt`, `Project_spec.txt`, `Functional_requirements.txt`, and `Non_Functional_requirements` for the full specification this build follows.

## Status

Phases 1-11 (scaffolding through the FastAPI API) are implemented. See `docs/architecture.md` for the full development order and current progress.

## Repository layout

```
backend/
  app/
    template_gen/    # template layout, JSON schema, PDF rendering (Phase 2)
    api/              # FastAPI routes + request/response schemas (Phase 11)
    services/         # job lifecycle: paths, uploads, status, pipeline orchestration, logging
    main.py           # FastAPI app
    config.py         # env-driven settings
  pipeline/
    preprocessing/ alignment/ segmentation/ validation/
    normalization/ vectorization/ font_generation/
    ink_geometry.py   # shared binary-image helpers
  tests/
  requirements.txt
frontend/            # Next.js app (Phase 12)
templates/           # generated template_v1.pdf / template_v1.json
jobs/                # per-job working directories (gitignored)
docs/
scripts/             # generate_template.py, run_pipeline.py (CLI)
```

Pydantic schemas live alongside the module that owns them (e.g. `pipeline/segmentation/schema.py`, `app/template_gen/schema.py`, `app/api/schemas.py`) rather than in one shared `models/` package — each stage's request/response shape is defined next to the code that produces it. `preview/`/`packaging/` pipeline packages and `output/` are still empty pending Phase 13.

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

## Run the full pipeline on photographed pages

```bash
backend/.venv/bin/python scripts/run_pipeline.py page1.jpg page2.jpg \
    --font-name "My Handwriting" --creator "Your Name"
```

Runs preprocessing → alignment → character extraction → validation → normalization → vectorization → font generation on one or more uploaded page photos, and prints a per-page and per-character summary. Each run gets an isolated `jobs/{job_id}/` directory (uploads/processed/glyphs/svg/font/preview/logs) and a structured JSON-lines log at `jobs/{job_id}/logs/pipeline.log`. Preview generation and ZIP packaging (spec §12-13) aren't implemented yet — this produces the TTF/OTF only.

## Run the API

```bash
backend/.venv/bin/uvicorn app.main:app --reload --app-dir backend
```

Serves the same pipeline over HTTP (interactive docs at `/docs`). Typical flow: `POST /api/jobs` → `POST /api/jobs/{id}/pages` (multipart upload) → `POST /api/jobs/{id}/process` (returns immediately; runs in the background) → poll `GET /api/jobs/{id}/status` until `"completed"` → `GET /api/jobs/{id}/validation` and `GET /api/jobs/{id}/download?format=ttf|otf`. `GET /api/templates` lists available templates. `/preview` isn't implemented yet (Phase 13).

## Run tests

```bash
cd backend
.venv/bin/python -m pytest -q
```
