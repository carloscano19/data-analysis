#!/bin/bash
# AI Data Analysis Tool — Dev Server Launcher
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
else
  source .venv/bin/activate
fi

echo ""
echo "  ✅  AI Data Analysis Tool"
echo "  🌐  http://localhost:8000"
echo ""

uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
