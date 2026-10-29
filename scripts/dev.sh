#!/usr/bin/env bash
# Starts the API (:8010) and the web app (:3000). Seeds demo data on first run.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d backend/.venv ] || { python3 -m venv backend/.venv && backend/.venv/bin/pip install -q -r backend/requirements.txt; }
[ -d frontend/node_modules ] || (cd frontend && npm install)
(cd backend && .venv/bin/python -m app.seed)
trap 'kill 0' EXIT
(cd backend && .venv/bin/uvicorn app.main:app --port 8010 --reload) &
(cd frontend && npm run dev -- -p 3000) &
wait
