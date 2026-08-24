gi# PersonalFont

Turn your own handwriting into a real, installable font (TTF/OTF).

Write your characters, photograph the page, and PersonalFont aligns, extracts, validates, and vectorizes each one into a font. The whole pipeline is deterministic, classical image processing — Otsu thresholding, connected-component analysis, ArUco-marker alignment, contour tracing — no generative AI, no invented glyphs. What you write is what you get.

## Features

- **Two ways to capture handwriting**
  - **Plain paper** — write every character on any blank sheet, in a shown order, and photograph it. No printer required.
  - **Printed template** — download a guided PDF with one box per character, fill it in, and photograph each page.
- **Automatic validation** — every character is checked for size, ink density, stray marks, and touching the box edge; flagged characters are called out with a specific reason.
- **Rewrite without reprinting** — fix just the flagged characters on a blank sheet of paper and re-submit, no matter which capture mode you started with.
- **Exclude characters on purpose** — leave a character out of the font even if it technically passed validation.
- **Live in-browser preview** — see your real generated font rendered with your own sample text before downloading.
- **Full download package** — TTF, OTF, PNG/PDF previews, individual SVG glyphs, metadata, and a README, all zipped together.

## Prerequisites

- Python 3.12+
- Node.js 20+
- `git`

No database, no external services — everything runs locally on the filesystem.

## Quick start

**One-liner:** `git clone <this-repo-url> personal-font && cd personal-font && ./run.sh` — sets up both the backend and frontend if needed, and starts them together (stop with Ctrl+C).

Or step by step:

Every command below is run from the **repository root** unless a `cd` is shown — copy-paste the whole block for a given step.

**1. Clone and set up the backend**

```bash
git clone <this-repo-url> personal-font
cd personal-font

python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
```

**2. Generate the handwriting template** (only needed for the printed-template capture mode)

```bash
backend/.venv/bin/python scripts/generate_template.py
```

Produces `templates/template_v1.pdf` (print this and hand-write the characters) and `templates/template_v1.json` (the data-driven description of every character box and alignment marker the pipeline reads).

**3. Start the API** (leave this running in its own terminal)

```bash
backend/.venv/bin/uvicorn app.main:app --reload --app-dir backend
```

API is now at `http://localhost:8000` (interactive docs at `/docs`).

**4. Start the frontend** (in a second terminal, from the repo root)

```bash
cd frontend
npm install
npm run dev
```

Open the URL it prints (Next.js picks the next free port starting at 3000). Walk through the wizard: write your characters (plain paper or a printed template) → upload the photo(s) → review any flagged characters → preview → download your font.

No frontend? Skip step 4 and drive the same pipeline from the CLI instead — see [Usage](#usage) below.

## Project structure

```
backend/
  app/
    template_gen/    # template layout, JSON schema, PDF rendering
    api/              # FastAPI routes + request/response schemas
    services/         # job lifecycle: paths, uploads, status, pipeline orchestration, logging
    main.py           # FastAPI app
    config.py         # env-driven settings
  pipeline/
    preprocessing/ alignment/ segmentation/ validation/
    normalization/ vectorization/ font_generation/
    preview/ packaging/   # preview PNG/PDF rendering, MyFont.zip assembly
    ink_geometry.py   # shared binary-image helpers
  tests/
  requirements.txt
frontend/            # Next.js app: capture -> processing -> review -> preview -> download
templates/           # generated template_v1.pdf / template_v1.json
jobs/                # per-job working directories (gitignored)
scripts/             # generate_template.py, run_pipeline.py (CLI)
```

Pydantic schemas live alongside the module that owns them (e.g. `pipeline/segmentation/schema.py`, `app/template_gen/schema.py`, `app/api/schemas.py`) rather than in one shared `models/` package — each stage's request/response shape is defined next to the code that produces it.

## Usage

### Run the full pipeline from the CLI

```bash
backend/.venv/bin/python scripts/run_pipeline.py page1.jpg page2.jpg \
    --font-name "My Handwriting" --creator "Your Name"
```

Runs preprocessing → alignment → character extraction → validation → normalization → vectorization → font generation → preview rendering → packaging on one or more uploaded page photos, and prints a per-page and per-character summary. Each run gets an isolated `jobs/{job_id}/` directory (`uploads/processed/glyphs/svg/font/preview/logs`) and a structured JSON-lines log at `jobs/{job_id}/logs/pipeline.log`. Produces `{name}.ttf`, `{name}.otf`, `preview.png`, `preview.pdf`, and `{name}.zip` (the full package: both fonts, both previews, a zip of the individual SVG glyphs, `metadata.json`, and `README.txt`).

### Run the API

```bash
backend/.venv/bin/uvicorn app.main:app --reload --app-dir backend
```

Two ways to start a job:

- **Plain paper:** `POST /api/jobs/freeform` (multipart photo upload, plus optional font metadata) — creates and processes a job in one call. `GET /api/character-set` returns the full ordered character list to write beforehand.
- **Printed template:** `POST /api/jobs` → `POST /api/jobs/{id}/pages` (multipart upload) → `POST /api/jobs/{id}/process`.

Either way: poll `GET /api/jobs/{id}/status` until `"completed"`, then `GET /api/jobs/{id}/validation` for the per-character results. From there:

- `GET /api/jobs/{id}/rewrite-list` / `POST /api/jobs/{id}/rewrite` — fix flagged characters with a new plain-paper photo, no reprinting.
- `POST /api/jobs/{id}/exclude` — rebuild the font leaving out specific characters on purpose.
- `GET /api/jobs/{id}/preview?format=png|pdf` and `GET /api/jobs/{id}/download?format=zip|ttf|otf` (`zip` is the default).

`GET /api/templates` lists available templates (`/{id}/pdf` downloads the printable template).

### Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Requires the API running separately at `http://localhost:8000` (override via `NEXT_PUBLIC_API_BASE_URL`); the backend's default CORS config already allows `localhost:3000` and `:3001`. See [`frontend/README.md`](frontend/README.md) for details.

### Run tests

```bash
backend/.venv/bin/python -m pytest -q --rootdir backend backend/tests
```

or, equivalently, from inside `backend/`:

```bash
cd backend
.venv/bin/python -m pytest -q
```
