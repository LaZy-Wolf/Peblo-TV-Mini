#!/bin/sh
set -e

echo "Applying migrations..."
alembic upgrade head

echo "Seeding content..."
python -m app.seed

echo "Publishing an initial catalogue..."
python -m app.bootstrap_publish

echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
