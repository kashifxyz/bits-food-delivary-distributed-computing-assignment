#!/bin/bash
echo "Cleaning build artifacts, caches, and temporary data..."
rm -rf frontend/dist frontend/node_modules/.vite
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type d -name ".pytest_cache" -exec rm -rf {} +
echo "Clean complete."
