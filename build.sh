#!/usr/bin/env bash
# Build-skript för Render — bygger både frontend och backend
set -e

echo "=== Installerar Python-dependencies ==="
pip install -r collector/requirements.txt

echo "=== Installerar Node-dependencies ==="
cd web
npm install

echo "=== Bygger Next.js (static export) ==="
npm run build

echo "=== Initierar databas ==="
cd ..
python -m collector.db.database

echo "=== Kör initial datainsamling ==="
python -m collector.main --init

echo "=== Build klar! ==="
