#!/bin/bash
cd "$(dirname "$0")/backend"
pkill -f "uvicorn app.main" 2>/dev/null
sleep 1
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 5173
