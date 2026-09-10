#!/bin/zsh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.local/node/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"
cd "$ROOT"

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/pip" install -r "$ROOT/backend/requirements.txt"
fi
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  (cd "$ROOT/frontend" && npm install)
fi

echo "AERA UI        http://127.0.0.1:3001"
echo "AERA API       http://127.0.0.1:8001/docs"
"$ROOT/.venv/bin/python" -m uvicorn main:app --app-dir "$ROOT/backend" --host 127.0.0.1 --port 8001 &
BACK=$!
trap 'kill $BACK' EXIT
cd "$ROOT/frontend" && npm run dev
