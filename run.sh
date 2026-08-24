#!/usr/bin/env bash
# Sets up (if needed) and runs the whole PersonalFont app: the FastAPI
# backend and the Next.js frontend, together, from the repo root.
#
# Usage: ./run.sh
# Stop both with Ctrl+C.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

BACKEND_DIR="backend"
FRONTEND_DIR="frontend"
VENV="$BACKEND_DIR/.venv"

echo "==> Checking backend setup"
if [ ! -d "$VENV" ]; then
  echo "Creating backend virtualenv..."
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"

echo "==> Checking frontend setup"
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "Installing frontend dependencies..."
  (cd "$FRONTEND_DIR" && npm install)
fi

if [ ! -f "templates/template_v1.pdf" ]; then
  echo "==> Generating the handwriting template"
  "$VENV/bin/python" scripts/generate_template.py
fi

cleanup() {
  echo
  echo "==> Stopping..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> Starting backend (http://localhost:8000, docs at /docs)"
"$VENV/bin/uvicorn" app.main:app --reload --app-dir "$BACKEND_DIR" &
BACKEND_PID=$!

echo "==> Starting frontend"
(cd "$FRONTEND_DIR" && npm run dev) &
FRONTEND_PID=$!

wait "$BACKEND_PID" "$FRONTEND_PID"
