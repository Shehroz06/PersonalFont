# PersonalFont — Frontend

Next.js (App Router, TypeScript, Tailwind) client for the PersonalFont pipeline (see the repo root `README.md` for the full project). Implements the capture-to-download wizard: Home → Write Freeform / Download Template → Upload → Processing → Character Review (→ Rewrite / Exclude) → Font Preview → Download.

Talks to the FastAPI backend entirely client-side via `fetch` — no server-side rendering of API data, no secrets on this side. All wizard state lives in `app/page.tsx`; each step is a component under `components/`.

## Setup

```bash
npm install
```

Backend URL defaults to `http://localhost:8000`. To point at a different backend, create `.env.local`:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Run

```bash
npm run dev
```

Next dev picks the next free port starting at 3000 — if something else is already using it, check the terminal output for the actual port. The backend's CORS default (`app/config.py`) allows both `http://localhost:3000` and `http://localhost:3001` for exactly this reason; set `PERSONALFONT_CORS_ORIGINS` on the backend if you land on a different port.

The backend must be running separately (`backend/.venv/bin/uvicorn app.main:app --reload --app-dir backend`) — this app has no API routes of its own.

## Notes

- **Character review's three states (✓/⚠/✗)** are derived on the frontend (`components/StepCharacterReview.tsx`) from the backend's binary `valid`/`invalid` `ValidationResult`, since the backend doesn't have a distinct "warning" state: a genuinely blank box (`"Empty glyph"`) reads as missing (✗); an invalid character with ink but a failed check reads as needing another look (⚠); `valid: true` reads as done (✓). See the comment in that file for the full reasoning.
- **Font preview** (`components/StepFontPreview.tsx`) downloads the real generated TTF, registers it as a `FontFace` from a blob URL, and renders sample text with it directly — a live, interactive preview rather than the static `preview.png`/`preview.pdf` the backend also generates (linked from the Download step). The two intentionally differ: the live preview falls back to the system font for characters missing from the font, while the static preview shows an honest `.notdef` gap.
- **Download step** (`components/StepDownload.tsx`) leads with the full `.zip` package and offers the individual `.ttf`/`.otf`/`preview.png`/`preview.pdf` files underneath.

## Build

```bash
npm run build
```
