#!/bin/bash
set -e
echo "Starting Frontend React (Vite) on http://localhost:5173..."
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR/frontend"

if command -v pnpm &> /dev/null; then
  pnpm run dev
elif command -v npm &> /dev/null; then
  npm run dev
fi
