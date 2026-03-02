#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Backend ──────────────────────────────────────────────────────────────────
echo "▶ Starting backend (FastAPI on :8000)…"
cd "$ROOT/backend"
uv sync --quiet
uv run uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

# ── Frontend ─────────────────────────────────────────────────────────────────
echo "▶ Starting frontend (Vite on :5173)…"
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  npm install --silent
fi
npm run dev &
FRONTEND_PID=$!

# ── Wait / cleanup ────────────────────────────────────────────────────────────
echo ""
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo ""
echo "  Press Ctrl-C to stop both servers."
echo ""

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
