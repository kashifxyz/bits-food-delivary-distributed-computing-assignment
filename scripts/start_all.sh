#!/bin/bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "========================================================="
echo " Starting Distributed Food Delivery System Monitor"
echo "========================================================="

# Start backend in background
./scripts/start_backend.sh &
BACKEND_PID=$!

# Wait for backend readiness
sleep 2

# Start frontend in background
./scripts/start_frontend.sh &
FRONTEND_PID=$!

echo "Backend running on PID $BACKEND_PID"
echo "Frontend running on PID $FRONTEND_PID"

trap "kill $BACKEND_PID $FRONTEND_PID" EXIT
wait
