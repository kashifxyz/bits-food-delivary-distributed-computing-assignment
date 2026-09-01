#!/bin/bash
echo "Stopping all background distributed monitoring services..."
pkill -f "uvicorn backend.app.main:app" || true
pkill -f "vite" || true
echo "Stopped."
