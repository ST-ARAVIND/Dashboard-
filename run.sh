#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Boots the backend (FastAPI/Uvicorn) and frontend (Vite) together.
# Usage:  ./run.sh            # install deps if needed, then run both
#         ./run.sh --no-install
# Stop with Ctrl-C (both processes are killed).
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
PYTHON="${PYTHON:-python3.12}"
INSTALL=1
[[ "${1:-}" == "--no-install" ]] && INSTALL=0

# --- .env check ---
if [[ ! -f "$ROOT/.env" ]]; then
  echo "⚠️  No .env found — copying .env.example to .env."
  echo "    Fill in your Angel One credentials before live data will work."
  cp "$ROOT/.env.example" "$ROOT/.env"
fi

# --- Backend deps ---
if [[ ! -d "$BACKEND/.venv" ]]; then
  echo "🐍 Creating Python venv ($PYTHON)…"
  "$PYTHON" -m venv "$BACKEND/.venv"
fi
if [[ "$INSTALL" == "1" ]]; then
  echo "🐍 Installing backend deps…"
  "$BACKEND/.venv/bin/python" -m pip install --quiet --upgrade pip
  "$BACKEND/.venv/bin/python" -m pip install --quiet -r "$BACKEND/requirements.txt"
fi

# --- Frontend deps ---
if [[ "$INSTALL" == "1" && ! -d "$FRONTEND/node_modules" ]]; then
  echo "📦 Installing frontend deps…"
  (cd "$FRONTEND" && npm install)
fi

# --- Run both ---
echo "🚀 Starting backend on :8000 and frontend on :5173"
PIDS=()
cleanup() {
  echo; echo "🛑 Shutting down…"
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(
  cd "$BACKEND"
  exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
) &
PIDS+=($!)

(
  cd "$FRONTEND"
  exec npm run dev
) &
PIDS+=($!)

echo "   Backend : http://127.0.0.1:8000  (docs at /docs)"
echo "   Frontend: http://localhost:5173"
wait
