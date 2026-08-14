# PersonalFont

A handwriting-to-font system that converts a user's handwritten template pages into a personalized installable font (TTF/OTF).

V1 is a deterministic pipeline — no generative AI, no model training. See `Initial_project_prompt.txt`, `Project_spec.txt`, `Functional_requirements.txt`, and `Non_Functional_requirements` for the full specification this build follows.

## Status

Phases 1-13 (scaffolding through preview + ZIP packaging) are implemented. See `docs/architecture.md` for the full development order and current progress.

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
    preview/ packaging/   # preview PNG/PDF rendering, MyFont.zip assembly (Phase 13)
    ink_geometry.py   # shared binary-image helpers
  tests/
  requirements.txt
frontend/            # Next.js app: upload -> processing -> review -> preview -> download (Phase 12)
templates/           # generated template_v1.pdf / template_v1.json
jobs/                # per-job working directories (gitignored)
docs/
scripts/             # generate_template.py, run_pipeline.py (CLI)
```

Pydantic schemas live alongside the module that owns them (e.g. `pipeline/segmentation/schema.py`, `app/template_gen/schema.py`, `app/api/schemas.py`) rather than in one shared `models/` package — each stage's request/response shape is defined next to the code that produces it.

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

Runs preprocessing → alignment → character extraction → validation → normalization → vectorization → font generation → preview rendering → packaging on one or more uploaded page photos, and prints a per-page and per-character summary. Each run gets an isolated `jobs/{job_id}/` directory (uploads/processed/glyphs/svg/font/preview/logs) and a structured JSON-lines log at `jobs/{job_id}/logs/pipeline.log`. Produces `{name}.ttf`, `{name}.otf`, `preview.png`, `preview.pdf`, and `{name}.zip` (the full spec §13 package: both fonts, both previews, a zip of the individual SVG glyphs, metadata.json, and README.txt).

## Run the API

```bash
backend/.venv/bin/uvicorn app.main:app --reload --app-dir backend
```

Serves the same pipeline over HTTP (interactive docs at `/docs`). Typical flow: `POST /api/jobs` → `POST /api/jobs/{id}/pages` (multipart upload) → `POST /api/jobs/{id}/process` (returns immediately; runs in the background) → poll `GET /api/jobs/{id}/status` until `"completed"` → `GET /api/jobs/{id}/validation`, `GET /api/jobs/{id}/preview?format=png|pdf`, and `GET /api/jobs/{id}/download?format=zip|ttf|otf` (`zip`, the full package, is the default). `GET /api/templates` lists available templates (and `/{id}/pdf` downloads the printable template).

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open the printed local URL (Next.js dev picks the next free port starting at 3000). Requires the API running separately at `http://localhost:8000` (override via `NEXT_PUBLIC_API_BASE_URL`); the backend's default CORS config already allows `localhost:3000` and `:3001`. See `frontend/README.md` for details.

## Run tests

```bash
cd backend
.venv/bin/python -m pytest -q
```
