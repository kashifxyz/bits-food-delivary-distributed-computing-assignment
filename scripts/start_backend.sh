#!/bin/bash
set -e
echo "Starting Backend Distributed Monitor on http://localhost:8000..."
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

if [ -d "backend/.venv" ]; then
  PYTHON_BIN="backend/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

export PYTHONPATH="$DIR"
$PYTHON_BIN -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
