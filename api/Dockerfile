FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so a source edit does not reinstall the world.
COPY api/pyproject.toml ./api/pyproject.toml
RUN pip install --upgrade pip && pip install "fastapi>=0.115" "uvicorn[standard]>=0.32" \
    "sqlalchemy>=2.0.36" "psycopg[binary]>=3.2" "alembic>=1.14" "pydantic-settings>=2.6" \
    "pyjwt>=2.10" "bcrypt>=4.2" "pillow>=11.0" "python-multipart>=0.0.17" "boto3>=1.35"

COPY api ./api
COPY data ./data

WORKDIR /app/api

# Migrate, seed, then publish a first catalogue, so `docker compose up` on a
# clean checkout hands the reviewer a browsable viewer with no manual steps.
# Every step is idempotent, so a restart is safe.
COPY api/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=40s --retries=5 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/healthz')"

ENTRYPOINT ["/entrypoint.sh"]
