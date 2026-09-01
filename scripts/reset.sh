#!/bin/bash
echo "Sending reset signal to distributed system backend..."
curl -X POST http://localhost:8000/api/processes/reset || echo "Backend not reachable."
