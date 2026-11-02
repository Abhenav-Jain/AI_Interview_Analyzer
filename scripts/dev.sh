#!/usr/bin/env bash
# Starts backend (:8000) and frontend (:5173) for local development.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || cp .env.example .env
(cd backend && python -m pip install -q -r requirements.txt && uvicorn app.main:get_app --factory --reload --port 8000) &
(cd frontend && npm install --no-audit --no-fund && npm run dev) &
wait
