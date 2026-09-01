# Peblo TV Mini Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI + PostgreSQL backend that stores shows/seasons/episodes/artwork, validates uploads, and publishes an immutable catalogue file that a viewer reads.

**Architecture:** SQLAlchemy 2.0 models behind Alembic migrations. Artwork is validated in-process with Pillow before it reaches a `Storage` Protocol implementation (local disk now, Cloudflare R2 by env var later). Publishing writes a run-scoped immutable JSON file and then flips a single-row pointer table in one transaction, which is the atomic commit point. The read path serves whatever the pointer names, cached in-process by run id.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pillow, PyJWT, bcrypt, pydantic-settings, pytest, httpx, ruff, PostgreSQL 16.

**Spec:** `docs/superpowers/specs/2026-09-01-peblo-tv-mini-design.md`

## Global Constraints

- Python 3.12. PostgreSQL 16.
- Vocabulary (sections, categories, languages, artwork specs) is read from `data/reference.json` at runtime. Never hardcode the lists in application code.
- Sections in canonical order: `featured`, `series`, `minisodes`, `songs`.
- Languages in canonical order: `en`, `hi`.
- Artwork specs: poster 2:3 at 600x900, banner 16:9 at 1280x720, thumbnail 16:9 at 640x360. All at or under 200 KB.
- Aspect tolerance 1%. Dimension tolerance 10% per axis.
- Roles: `editor` and `admin`. Every `/admin/*` route declares `require_editor` or `require_admin` as a FastAPI dependency. No route reads the role and branches inside its body.
- Error envelope on every 4xx: `{"errors": [{"code": str, "message": str, "field": str | None}]}`. Messages are readable by a non-technical content editor. Multiple problems return together, never one at a time.
- No em dashes in any user-facing message string.
- All timestamps are timezone-aware UTC.
- Every task ends green: `ruff check api` and `pytest api/tests` both pass before the commit.

---

## File Structure

| File | Responsibility |
|---|---|
| `api/pyproject.toml` | Dependencies, ruff and pytest config |
| `api/app/config.py` | Every env var, declared once via pydantic-settings |
| `api/app/reference.py` | Loads and exposes `data/reference.json` |
| `api/app/db.py` | Engine, session factory, FastAPI session dependency |
| `api/app/models.py` | All SQLAlchemy models |
| `api/app/schemas.py` | Pydantic request and response models |
| `api/app/errors.py` | Error envelope and the exception handler |
| `api/app/auth.py` | Password hashing, JWT issue/verify, role dependencies |
| `api/app/storage/base.py` | `Storage` Protocol |
| `api/app/storage/local.py` | `LocalDiskStorage` |
| `api/app/storage/r2.py` | `R2Storage` |
| `api/app/storage/__init__.py` | `get_storage()` backend selection |
| `api/app/artwork.py` | Image validation, pure function, no I/O |
| `api/app/validation.py` | Validation report rules |
| `api/app/catalog/build.py` | Catalogue construction from the database |
| `api/app/catalog/publish.py` | Run orchestration and the pointer flip |
| `api/app/catalog/serve.py` | Cached read path |
| `api/app/catalog/search.py` | In-memory query over the cached catalogue |
| `api/app/seed.py` | Seed loader, import issue recording |
| `api/app/routers/*.py` | One router per resource |
| `api/alembic/` | Migrations |
| `api/tests/` | pytest suite |
| `docker-compose.yml` | `db` service in Task 1, extended by the pipeline plan |

---

### Task 1: Scaffold, config, health endpoint, test harness

**Files:**
- Create: `api/pyproject.toml`, `api/app/__init__.py`, `api/app/config.py`, `api/app/reference.py`, `api/app/errors.py`, `api/app/main.py`, `api/app/routers/__init__.py`, `api/app/routers/health.py`
- Create: `api/tests/__init__.py`, `api/tests/conftest.py`, `api/tests/test_health.py`
- Create: `docker-compose.yml`, `.env.example`
- Create: `data/` by copying `Data-Given/seed_shows.json`, `Data-Given/reference.json`, and the six images into `data/assets/`

**Interfaces:**
- Consumes: nothing
- Produces: `settings` (a `Settings` instance) from `app.config`; `reference()` returning a `Reference` dataclass with `sections: list[str]`, `categories: list[str]`, `languages: list[str]`, `artwork_specs: dict[str, ArtworkSpec]`; `app` (FastAPI instance) from `app.main`; `error_response(errors) -> JSONResponse` from `app.errors`; pytest fixture `client` (httpx test client)

- [ ] **Step 1: Copy the supplied data into the repo**

```bash
mkdir -p data/assets
cp Data-Given/seed_shows.json data/seed_shows.json
cp Data-Given/reference.json data/reference.json
cp Data-Given/*.jpg Data-Given/*.png data/assets/
```

- [ ] **Step 2: Write `api/pyproject.toml`**

```toml
[project]
name = "peblo-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy>=2.0.36",
    "psycopg[binary]>=3.2",
    "alembic>=1.14",
    "pydantic-settings>=2.6",
    "pyjwt>=2.10",
    "bcrypt>=4.2",
    "pillow>=11.0",
    "python-multipart>=0.0.17",
    "boto3>=1.35",
]

[project.optional-dependencies]
dev = ["pytest>=8.3", "httpx>=0.28", "ruff>=0.8"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pytest.ini_options]
testpaths = ["tests"]
filterwarnings = ["error::DeprecationWarning"]
```

- [ ] **Step 3: Write `docker-compose.yml` with only the database**

The pipeline plan extends this file. For now it exists so tests have a real PostgreSQL to run against.

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: peblo
      POSTGRES_PASSWORD: peblo
      POSTGRES_DB: peblo
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U peblo"]
      interval: 3s
      timeout: 3s
      retries: 20
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

- [ ] **Step 4: Write `.env.example`**

Every variable the system reads, each with a comment. The pipeline plan adds the frontend variables.

```bash
# --- Database ---
# Full SQLAlchemy URL. In compose the host is the service name `db`.
DATABASE_URL=postgresql+psycopg://peblo:peblo@localhost:5432/peblo
# Separate database used by the test suite. Created and dropped by pytest.
TEST_DATABASE_URL=postgresql+psycopg://peblo:peblo@localhost:5432/peblo_test

# --- Auth ---
# Signing key for JWTs. Generate with: openssl rand -hex 32
# In production this comes from a secret manager, never from a file in the repo.
JWT_SECRET=dev-only-change-me
JWT_EXPIRY_HOURS=8
# Passwords for the two seeded accounts. Dev values only.
SEED_EDITOR_EMAIL=editor@peblo.test
SEED_EDITOR_PASSWORD=editor-dev-password
SEED_ADMIN_EMAIL=admin@peblo.test
SEED_ADMIN_PASSWORD=admin-dev-password

# --- Storage ---
# One of: local | r2
STORAGE_BACKEND=local
# Filesystem root when STORAGE_BACKEND=local
STORAGE_LOCAL_ROOT=./storage_local
# Public URL prefix that artwork keys are appended to
STORAGE_PUBLIC_BASE_URL=http://localhost:8000/media

# --- Cloudflare R2 (only when STORAGE_BACKEND=r2) ---
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=
# https://<account-id>.r2.cloudflarestorage.com
R2_ENDPOINT_URL=

# --- App ---
# Directory holding reference.json, seed_shows.json and assets/
DATA_DIR=./data
# Comma separated origins allowed to call the API
CORS_ORIGINS=http://localhost:5173,http://localhost:5174
```

- [ ] **Step 5: Write `api/app/config.py`**

```python
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://peblo:peblo@localhost:5432/peblo"
    test_database_url: str = "postgresql+psycopg://peblo:peblo@localhost:5432/peblo_test"

    jwt_secret: str = "dev-only-change-me"
    jwt_expiry_hours: int = 8
    seed_editor_email: str = "editor@peblo.test"
    seed_editor_password: str = "editor-dev-password"
    seed_admin_email: str = "admin@peblo.test"
    seed_admin_password: str = "admin-dev-password"

    storage_backend: str = "local"
    storage_local_root: Path = Path("./storage_local")
    storage_public_base_url: str = "http://localhost:8000/media"

    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    r2_endpoint_url: str = ""

    data_dir: Path = Path("./data")
    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

- [ ] **Step 6: Write `api/app/reference.py`**

```python
import json
from dataclasses import dataclass
from functools import lru_cache

from app.config import settings


@dataclass(frozen=True)
class ArtworkSpec:
    kind: str
    aspect_w: int
    aspect_h: int
    target_w: int
    target_h: int
    max_kb: int

    @property
    def aspect(self) -> float:
        return self.aspect_w / self.aspect_h


@dataclass(frozen=True)
class Reference:
    sections: list[str]
    categories: list[str]
    languages: list[str]
    artwork_specs: dict[str, ArtworkSpec]

    def section_order(self, section: str | None) -> int:
        return self.sections.index(section) if section in self.sections else len(self.sections)

    def language_order(self, language: str) -> int:
        return (
            self.languages.index(language)
            if language in self.languages
            else len(self.languages)
        )

    def sort_languages(self, languages: list[str]) -> list[str]:
        return sorted(set(languages), key=self.language_order)


@lru_cache
def reference() -> Reference:
    raw = json.loads((settings.data_dir / "reference.json").read_text(encoding="utf-8"))
    specs = {}
    for kind, spec in raw["artwork_specs"].items():
        aw, ah = (int(p) for p in spec["aspect"].split(":"))
        specs[kind] = ArtworkSpec(
            kind=kind,
            aspect_w=aw,
            aspect_h=ah,
            target_w=spec["target_px"][0],
            target_h=spec["target_px"][1],
            max_kb=spec["max_kb"],
        )
    return Reference(
        sections=list(raw["sections"]),
        categories=list(raw["categories"]),
        languages=list(raw["languages"]),
        artwork_specs=specs,
    )
```

- [ ] **Step 7: Write `api/app/errors.py`**

```python
from dataclasses import asdict, dataclass

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass
class ApiError:
    code: str
    message: str
    field: str | None = None


class ApiException(Exception):
    def __init__(self, status_code: int, errors: list[ApiError]):
        self.status_code = status_code
        self.errors = errors


def error_response(status_code: int, errors: list[ApiError]) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"errors": [asdict(e) for e in errors]},
    )


async def api_exception_handler(_: Request, exc: ApiException) -> JSONResponse:
    return error_response(exc.status_code, exc.errors)
```

- [ ] **Step 8: Write `api/app/routers/health.py`**

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness only. Deliberately touches no dependency, so a database blip
    does not cause the orchestrator to kill an otherwise healthy container."""
    return {"status": "ok"}
```

- [ ] **Step 9: Write `api/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.errors import ApiException, api_exception_handler
from app.routers import health

app = FastAPI(title="Peblo TV Mini API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(ApiException, api_exception_handler)
app.include_router(health.router)
```

- [ ] **Step 10: Write `api/tests/conftest.py`**

This fixture builds the test database once per session. Later tasks extend it with a database session fixture; for now it only needs to give tests an HTTP client.

```python
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
os.environ.setdefault("DATA_DIR", str(ROOT / "data"))


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)
```

- [ ] **Step 11: Write the failing test**

`api/tests/test_health.py`:

```python
def test_healthz_returns_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_reference_loads_expected_vocabulary():
    from app.reference import reference

    ref = reference()
    assert ref.sections == ["featured", "series", "minisodes", "songs"]
    assert ref.languages == ["en", "hi"]
    assert len(ref.categories) == 15
    assert ref.artwork_specs["poster"].target_w == 600
    assert ref.artwork_specs["poster"].target_h == 900
    assert ref.artwork_specs["banner"].max_kb == 200


def test_language_sort_uses_reference_order():
    from app.reference import reference

    assert reference().sort_languages(["hi", "en"]) == ["en", "hi"]
```

- [ ] **Step 12: Run tests to verify they fail**

Run: `cd api && python -m pytest tests/test_health.py -v`
Expected: FAIL, collection error on `ModuleNotFoundError: No module named 'app'` before the files exist, then passing once steps 5 through 9 are in place.

- [ ] **Step 13: Install and run tests to verify they pass**

```bash
cd api && pip install -e ".[dev]" && python -m pytest tests -v && ruff check .
```
Expected: 3 passed, ruff clean.

- [ ] **Step 14: Commit**

```bash
git add api data docker-compose.yml .env.example
git commit -m "feat(api): scaffold, config, reference loader, health endpoint"
```

---

### Task 2: Data model and first migration

**Files:**
- Create: `api/app/db.py`, `api/app/models.py`, `api/alembic.ini`, `api/alembic/env.py`, `api/alembic/script.py.mako`, `api/alembic/versions/0001_initial.py`
- Modify: `api/tests/conftest.py`
- Test: `api/tests/test_models.py`

**Interfaces:**
- Consumes: `settings` from Task 1
- Produces: `Base`, and models `User`, `Show`, `Season`, `Episode`, `Artwork`, `PublishRun`, `CatalogPointer`, `ImportIssue` from `app.models`; enums `Role`, `ContentStatus`, `RunStatus`, `ArtworkKind`, `ImportAction`; `get_session()` FastAPI dependency and `SessionLocal` from `app.db`; pytest fixtures `db` (a `Session` rolled back after each test) and `engine`

- [ ] **Step 1: Write `api/app/db.py`**

```python
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 2: Write `api/app/models.py`**

```python
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Role(str, enum.Enum):
    editor = "editor"
    admin = "admin"


class ContentStatus(str, enum.Enum):
    draft = "draft"
    published = "published"


class RunStatus(str, enum.Enum):
    running = "running"
    success = "success"
    failed = "failed"
    no_change = "no_change"


class ArtworkKind(str, enum.Enum):
    poster = "poster"
    banner = "banner"
    thumbnail = "thumbnail"


class ImportAction(str, enum.Enum):
    rejected = "rejected"
    downgraded_to_draft = "downgraded_to_draft"


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = _now()


class Show(Base):
    __tablename__ = "shows"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    synopsis: Mapped[str] = mapped_column(Text, default="", nullable=False)
    section: Mapped[str | None] = mapped_column(String(32))
    categories: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    status: Mapped[ContentStatus] = mapped_column(
        String(16), default=ContentStatus.draft, nullable=False
    )
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    seasons: Mapped[list["Season"]] = relationship(
        back_populates="show", cascade="all, delete-orphan"
    )
    artwork: Mapped[list["Artwork"]] = relationship(
        back_populates="show", cascade="all, delete-orphan"
    )

    # Serves both the publish query and the validation report, which share this predicate.
    __table_args__ = (Index("ix_shows_status_section", "status", "section"),)


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    show_id: Mapped[int] = mapped_column(ForeignKey("shows.id", ondelete="CASCADE"), nullable=False)
    season_number: Mapped[int] = mapped_column(Integer, nullable=False)

    show: Mapped[Show] = relationship(back_populates="seasons")
    episodes: Mapped[list["Episode"]] = relationship(
        back_populates="season", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("show_id", "season_number", name="uq_seasons_show_number"),)


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    content_group: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[ContentStatus] = mapped_column(
        String(16), default=ContentStatus.draft, nullable=False
    )
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    season: Mapped[Season] = relationship(back_populates="episodes")
    artwork: Mapped[list["Artwork"]] = relationship(
        back_populates="episode", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # The brief's constraint, enforced by the database so a concurrent
        # write cannot slip past it. Also the grouping key at build time.
        UniqueConstraint("content_group", "language", name="uq_episodes_group_language"),
        Index("ix_episodes_season_number", "season_id", "episode_number"),
    )


class Artwork(Base):
    __tablename__ = "artwork"

    id: Mapped[int] = mapped_column(primary_key=True)
    show_id: Mapped[int | None] = mapped_column(ForeignKey("shows.id", ondelete="CASCADE"))
    episode_id: Mapped[int | None] = mapped_column(ForeignKey("episodes.id", ondelete="CASCADE"))
    kind: Mapped[ArtworkKind] = mapped_column(String(16), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _now()

    show: Mapped[Show | None] = relationship(back_populates="artwork")
    episode: Mapped[Episode | None] = relationship(back_populates="artwork")

    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(show_id, episode_id) = 1", name="ck_artwork_exactly_one_owner"
        ),
    )


class PublishRun(Base):
    __tablename__ = "publish_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    started_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime] = _now()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[RunStatus] = mapped_column(String(16), nullable=False)
    catalog_key: Mapped[str | None] = mapped_column(String(512))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    counts: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (Index("ix_publish_runs_started_at", started_at.desc()),)


class CatalogPointer(Base):
    __tablename__ = "catalog_pointer"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    current_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("publish_runs.id", ondelete="RESTRICT")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (CheckConstraint("id = 1", name="ck_catalog_pointer_singleton"),)


class ImportIssue(Base):
    __tablename__ = "import_issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_row: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[ImportAction] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = _now()
```

- [ ] **Step 3: Initialise Alembic and write the migration**

```bash
cd api && alembic init -t async alembic 2>/dev/null || alembic init alembic
```

Replace `api/alembic/env.py` entirely with:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url, target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Generate and hand-check the initial migration**

```bash
cd api && docker compose -f ../docker-compose.yml up -d db && alembic revision --autogenerate -m "initial schema"
```

Rename the generated file to `api/alembic/versions/0001_initial.py`. Autogenerate does not emit the GIN index or the singleton pointer row, so append these to its `upgrade()`:

```python
    op.execute(
        "CREATE INDEX ix_shows_categories_gin ON shows USING GIN (categories)"
    )
    op.execute("INSERT INTO catalog_pointer (id, current_run_id) VALUES (1, NULL)")
```

And prepend to `downgrade()`:

```python
    op.execute("DROP INDEX IF EXISTS ix_shows_categories_gin")
```

- [ ] **Step 5: Add database fixtures to `api/tests/conftest.py`**

Append:

```python
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="session")
def engine():
    from app.config import settings

    admin_url = settings.database_url.rsplit("/", 1)[0] + "/postgres"
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS peblo_test WITH (FORCE)"))
        conn.execute(text("CREATE DATABASE peblo_test"))
    admin.dispose()

    test_engine = create_engine(settings.test_database_url)
    from app.models import Base

    Base.metadata.create_all(test_engine)
    with test_engine.begin() as conn:
        conn.execute(text("CREATE INDEX ix_shows_categories_gin ON shows USING GIN (categories)"))
        conn.execute(text("INSERT INTO catalog_pointer (id, current_run_id) VALUES (1, NULL)"))
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db(engine):
    """A session that is rolled back after each test, so tests never see
    each other's rows and order of execution cannot matter."""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, expire_on_commit=False)()
    yield session
    session.close()
    transaction.rollback()
    connection.close()
```

- [ ] **Step 6: Write the failing test**

`api/tests/test_models.py`:

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import ContentStatus, Episode, Season, Show


def _show(db, slug="s1"):
    show = Show(slug=slug, title="T", synopsis="", section="series", categories=["music"])
    db.add(show)
    db.flush()
    season = Season(show_id=show.id, season_number=1)
    db.add(season)
    db.flush()
    return show, season


def test_content_group_language_pair_is_unique(db):
    _, season = _show(db)
    db.add(
        Episode(
            season_id=season.id,
            episode_number=1,
            title="A",
            language="hi",
            content_group="g1",
            status=ContentStatus.published,
        )
    )
    db.flush()
    db.add(
        Episode(
            season_id=season.id,
            episode_number=2,
            title="B",
            language="hi",
            content_group="g1",
            status=ContentStatus.published,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_same_content_group_different_language_is_allowed(db):
    _, season = _show(db)
    for i, lang in enumerate(["en", "hi"], start=1):
        db.add(
            Episode(
                season_id=season.id,
                episode_number=i,
                title="A",
                language=lang,
                content_group="g1",
            )
        )
    db.flush()
    assert db.query(Episode).count() == 2


def test_artwork_requires_exactly_one_owner(db):
    from app.models import Artwork, ArtworkKind

    db.add(
        Artwork(
            show_id=None,
            episode_id=None,
            kind=ArtworkKind.poster,
            storage_key="k",
            width=600,
            height=900,
            bytes=100,
            checksum="c",
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_show_slug_is_unique(db):
    _show(db, "dup")
    db.add(Show(slug="dup", title="T2", synopsis="", categories=[]))
    with pytest.raises(IntegrityError):
        db.flush()
```

- [ ] **Step 7: Run tests to verify they fail then pass**

Run: `cd api && python -m pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models'` before step 2, PASS (4 passed) after steps 2 and 5.

- [ ] **Step 8: Verify the migration applies cleanly from empty**

```bash
cd api && alembic downgrade base && alembic upgrade head && alembic check
```
Expected: no error, and `alembic check` reports no pending changes, which proves the migration matches the models.

- [ ] **Step 9: Commit**

```bash
git add api/app/db.py api/app/models.py api/alembic api/alembic.ini api/tests
git commit -m "feat(api): schema, initial migration, database test fixtures"
```

---

### Task 3: Auth, roles, and enforcement

**Files:**
- Create: `api/app/auth.py`, `api/app/routers/auth.py`
- Modify: `api/app/main.py`, `api/tests/conftest.py`
- Test: `api/tests/test_auth.py`

**Interfaces:**
- Consumes: `User`, `Role` from Task 2; `ApiError`, `ApiException` from Task 1
- Produces: `hash_password(plain: str) -> str`, `verify_password(plain: str, hashed: str) -> bool`, `create_token(user: User) -> str`, `current_user(...) -> User`, `require_editor(...) -> User`, `require_admin(...) -> User` from `app.auth`; pytest fixtures `editor_token`, `admin_token`, `api` (a client wired to the test database)

- [ ] **Step 1: Write `api/app/auth.py`**

```python
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.errors import ApiError, ApiException
from app.models import Role, User

_scheme = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value if isinstance(user.role, Role) else user.role,
        "exp": datetime.now(UTC) + timedelta(hours=settings.jwt_expiry_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _unauthorized() -> ApiException:
    return ApiException(
        401,
        [ApiError("not_authenticated", "Please sign in to continue.")],
    )


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_scheme),
    session: Session = Depends(get_session),
) -> User:
    if credentials is None:
        raise _unauthorized()
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise _unauthorized() from exc
    user = session.get(User, int(payload["sub"]))
    if user is None:
        raise _unauthorized()
    return user


def require_editor(user: User = Depends(current_user)) -> User:
    """Both roles may read and write content."""
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    role = user.role.value if isinstance(user.role, Role) else user.role
    if role != Role.admin.value:
        raise ApiException(
            403,
            [
                ApiError(
                    "forbidden",
                    "Publishing is restricted to administrators. "
                    "Ask an administrator to publish, or request admin access.",
                )
            ],
        )
    return user
```

- [ ] **Step 2: Write `api/app/routers/auth.py`**

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_token, current_user, verify_password
from app.db import get_session
from app.errors import ApiError, ApiException
from app.models import Role, User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    role: str
    email: str


class MeResponse(BaseModel):
    id: int
    email: str
    role: str


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    user = session.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise ApiException(
            401,
            [ApiError("invalid_credentials", "That email and password do not match.")],
        )
    role = user.role.value if isinstance(user.role, Role) else user.role
    return TokenResponse(access_token=create_token(user), role=role, email=user.email)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(current_user)) -> MeResponse:
    role = user.role.value if isinstance(user.role, Role) else user.role
    return MeResponse(id=user.id, email=user.email, role=role)
```

- [ ] **Step 3: Register the router in `api/app/main.py`**

Add the import and include line:

```python
from app.routers import auth, health

app.include_router(auth.router)
```

- [ ] **Step 4: Add auth fixtures to `api/tests/conftest.py`**

Append. The `api` fixture is what every later HTTP test uses, because it overrides `get_session` so requests hit the rolled-back test session rather than the real database.

```python
@pytest.fixture
def api(db):
    from fastapi.testclient import TestClient

    from app.db import get_session
    from app.main import app

    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def users(db):
    from app.auth import hash_password
    from app.models import Role, User

    editor = User(email="editor@peblo.test", password_hash=hash_password("pw"), role=Role.editor)
    admin = User(email="admin@peblo.test", password_hash=hash_password("pw"), role=Role.admin)
    db.add_all([editor, admin])
    db.flush()
    return {"editor": editor, "admin": admin}


@pytest.fixture
def editor_headers(users):
    from app.auth import create_token

    return {"Authorization": f"Bearer {create_token(users['editor'])}"}


@pytest.fixture
def admin_headers(users):
    from app.auth import create_token

    return {"Authorization": f"Bearer {create_token(users['admin'])}"}
```

- [ ] **Step 5: Write the failing test**

`api/tests/test_auth.py`:

```python
def test_login_returns_token_and_role(api, users):
    response = api.post("/auth/login", json={"email": "admin@peblo.test", "password": "pw"})
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "admin"
    assert body["access_token"]


def test_login_with_wrong_password_is_rejected(api, users):
    response = api.post("/auth/login", json={"email": "admin@peblo.test", "password": "nope"})
    assert response.status_code == 401
    assert response.json()["errors"][0]["code"] == "invalid_credentials"


def test_me_requires_a_token(api, users):
    assert api.get("/auth/me").status_code == 401


def test_me_returns_the_caller(api, editor_headers):
    response = api.get("/auth/me", headers=editor_headers)
    assert response.status_code == 200
    assert response.json()["role"] == "editor"


# Registered once at import time. Do NOT register this inside a test body:
# the second test would then depend on the first having run, and the suite
# would break the moment someone runs a single test with -k.
def _register_probe_route() -> None:
    from fastapi import Depends

    from app.auth import require_admin
    from app.main import app

    if any(getattr(r, "path", None) == "/_test_admin_only" for r in app.routes):
        return

    @app.get("/_test_admin_only")
    def _admin_only(_=Depends(require_admin)):
        return {"ok": True}


_register_probe_route()


def test_require_admin_rejects_an_editor(api, editor_headers):
    """The role gate is a dependency, so this proves enforcement without
    needing a real admin route to exist yet."""
    response = api.get("/_test_admin_only", headers=editor_headers)
    assert response.status_code == 403
    assert response.json()["errors"][0]["code"] == "forbidden"


def test_require_admin_allows_an_admin(api, admin_headers):
    response = api.get("/_test_admin_only", headers=admin_headers)
    assert response.status_code == 200
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd api && python -m pytest tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth'`.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd api && python -m pytest tests -v && ruff check .`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add api/app/auth.py api/app/routers/auth.py api/app/main.py api/tests
git commit -m "feat(api): JWT auth with editor and admin role dependencies"
```

---

### Task 4: Storage abstraction

**Files:**
- Create: `api/app/storage/__init__.py`, `api/app/storage/base.py`, `api/app/storage/local.py`, `api/app/storage/r2.py`
- Test: `api/tests/test_storage.py`

**Interfaces:**
- Consumes: `settings` from Task 1
- Produces: `Storage` Protocol with `put(key, data, content_type) -> str`, `get(key) -> bytes`, `url(key) -> str`, `exists(key) -> bool`, `delete(key) -> None`; `LocalDiskStorage(root, public_base_url)`; `R2Storage(...)`; `get_storage() -> Storage`

- [ ] **Step 1: Write `api/app/storage/base.py`**

```python
from typing import Protocol


class Storage(Protocol):
    """The only surface the rest of the application may depend on.

    Moving from local disk to Cloudflare R2 is a change of implementation
    and environment variables, never a change of call site.
    """

    def put(self, key: str, data: bytes, content_type: str) -> str:
        """Write bytes at key. Returns the public URL."""

    def get(self, key: str) -> bytes: ...

    def url(self, key: str) -> str: ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None: ...


class ObjectNotFound(Exception):
    pass
```

- [ ] **Step 2: Write `api/app/storage/local.py`**

```python
from pathlib import Path

from app.storage.base import ObjectNotFound


class LocalDiskStorage:
    def __init__(self, root: Path, public_base_url: str):
        self.root = Path(root)
        self.public_base_url = public_base_url.rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError("key escapes storage root")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return self.url(key)

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise ObjectNotFound(key)
        return path.read_bytes()

    def url(self, key: str) -> str:
        return f"{self.public_base_url}/{key}"

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
```

- [ ] **Step 3: Write `api/app/storage/r2.py`**

```python
import boto3
from botocore.exceptions import ClientError

from app.storage.base import ObjectNotFound


class R2Storage:
    """Cloudflare R2 is S3 compatible, so this is boto3 pointed at R2's endpoint.

    Written but not verified against a live bucket, because this exercise has
    no bucket to verify against. The README says so rather than implying it works.
    """

    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        endpoint_url: str,
        public_base_url: str,
    ):
        self.bucket = bucket
        self.public_base_url = public_base_url.rstrip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

    def put(self, key: str, data: bytes, content_type: str) -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return self.url(key)

    def get(self, key: str) -> bytes:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as exc:
            raise ObjectNotFound(key) from exc

    def url(self, key: str) -> str:
        return f"{self.public_base_url}/{key}"

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)
```

- [ ] **Step 4: Write `api/app/storage/__init__.py`**

```python
from functools import lru_cache

from app.config import settings
from app.storage.base import ObjectNotFound, Storage
from app.storage.local import LocalDiskStorage
from app.storage.r2 import R2Storage

__all__ = ["Storage", "ObjectNotFound", "LocalDiskStorage", "R2Storage", "get_storage"]


@lru_cache
def get_storage() -> Storage:
    if settings.storage_backend == "r2":
        return R2Storage(
            account_id=settings.r2_account_id,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            bucket=settings.r2_bucket,
            endpoint_url=settings.r2_endpoint_url,
            public_base_url=settings.storage_public_base_url,
        )
    return LocalDiskStorage(settings.storage_local_root, settings.storage_public_base_url)
```

- [ ] **Step 5: Write the failing test**

`api/tests/test_storage.py`:

```python
import pytest

from app.storage import LocalDiskStorage, ObjectNotFound


@pytest.fixture
def storage(tmp_path):
    return LocalDiskStorage(tmp_path, "http://example.test/media")


def test_put_then_get_roundtrips(storage):
    storage.put("a/b/c.jpg", b"hello", "image/jpeg")
    assert storage.get("a/b/c.jpg") == b"hello"


def test_put_returns_public_url(storage):
    assert storage.put("k.jpg", b"x", "image/jpeg") == "http://example.test/media/k.jpg"


def test_exists_reflects_reality(storage):
    assert storage.exists("nope.jpg") is False
    storage.put("yes.jpg", b"x", "image/jpeg")
    assert storage.exists("yes.jpg") is True


def test_get_missing_raises(storage):
    with pytest.raises(ObjectNotFound):
        storage.get("missing.jpg")


def test_delete_is_idempotent(storage):
    storage.put("d.jpg", b"x", "image/jpeg")
    storage.delete("d.jpg")
    storage.delete("d.jpg")
    assert storage.exists("d.jpg") is False


def test_key_cannot_escape_the_root(storage):
    with pytest.raises(ValueError):
        storage.put("../escape.jpg", b"x", "image/jpeg")


def test_r2_storage_satisfies_the_same_protocol():
    """Constructed with dummy credentials and never called, so no network.
    This exists to catch a signature drifting apart from LocalDiskStorage."""
    from app.storage import R2Storage

    for method in ("put", "get", "url", "exists", "delete"):
        assert callable(getattr(R2Storage, method))
    assert (
        R2Storage.put.__code__.co_varnames[:4]
        == LocalDiskStorage.put.__code__.co_varnames[:4]
    )
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd api && python -m pytest tests/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.storage'`.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd api && python -m pytest tests/test_storage.py -v`
Expected: 7 passed.

- [ ] **Step 8: Commit**

```bash
git add api/app/storage api/tests/test_storage.py
git commit -m "feat(api): storage abstraction with local disk and R2 implementations"
```

---

### Task 5: Artwork validation

**Files:**
- Create: `api/app/artwork.py`
- Test: `api/tests/test_artwork_validation.py`

**Interfaces:**
- Consumes: `reference()`, `ArtworkSpec` from Task 1; `ApiError` from Task 1
- Produces: `validate_artwork(kind: str, data: bytes) -> ArtworkMeta` raising `ApiException(422, errors)`; `ArtworkMeta` dataclass with `width: int`, `height: int`, `bytes: int`, `checksum: str`, `content_type: str`

- [ ] **Step 1: Write the failing test**

`api/tests/test_artwork_validation.py`. Note that the last test generates its own oversized file, because no supplied asset reaches the 200 KB ceiling and an untested rule is an unkept promise.

```python
import io
from pathlib import Path

import pytest
from PIL import Image

from app.config import settings
from app.errors import ApiException

ASSETS = Path(settings.data_dir) / "assets"


def _read(name: str) -> bytes:
    return (ASSETS / name).read_bytes()


def _codes(exc: ApiException) -> set[str]:
    return {e.code for e in exc.errors}


def test_good_poster_is_accepted():
    from app.artwork import validate_artwork

    meta = validate_artwork("poster", _read("poster_good.jpg"))
    assert (meta.width, meta.height) == (600, 900)
    assert meta.content_type == "image/jpeg"
    assert len(meta.checksum) == 64


def test_good_banner_is_accepted():
    from app.artwork import validate_artwork

    meta = validate_artwork("banner", _read("banner_good.jpg"))
    assert (meta.width, meta.height) == (1280, 720)


def test_good_thumbnail_is_accepted():
    from app.artwork import validate_artwork

    meta = validate_artwork("thumbnail", _read("thumb_good.jpg"))
    assert (meta.width, meta.height) == (640, 360)


def test_rotated_poster_is_rejected_on_aspect():
    from app.artwork import validate_artwork

    with pytest.raises(ApiException) as exc:
        validate_artwork("poster", _read("poster_wrong_ratio.jpg"))
    assert "artwork_wrong_aspect" in _codes(exc.value)


def test_oversized_banner_is_rejected_on_dimensions_not_bytes():
    """banner_too_big.png is 2560x1440 at 13.8 KB. It passes the byte ceiling
    comfortably, so a validator that only weighs files would wave it through."""
    from app.artwork import validate_artwork

    with pytest.raises(ApiException) as exc:
        validate_artwork("banner", _read("banner_too_big.png"))
    codes = _codes(exc.value)
    assert "artwork_wrong_dimensions" in codes
    assert "artwork_too_large" not in codes


def test_tiny_thumbnail_is_rejected_on_dimensions():
    from app.artwork import validate_artwork

    with pytest.raises(ApiException) as exc:
        validate_artwork("thumbnail", _read("thumb_tiny.jpg"))
    assert "artwork_wrong_dimensions" in _codes(exc.value)


def test_file_over_200kb_is_rejected():
    from app.artwork import validate_artwork

    buffer = io.BytesIO()
    Image.effect_noise((600, 900), 120).convert("RGB").save(buffer, format="PNG")
    data = buffer.getvalue()
    assert len(data) > 200 * 1024, "fixture must actually exceed the ceiling"
    with pytest.raises(ApiException) as exc:
        validate_artwork("poster", data)
    assert "artwork_too_large" in _codes(exc.value)


def test_non_image_is_rejected():
    from app.artwork import validate_artwork

    with pytest.raises(ApiException) as exc:
        validate_artwork("poster", b"this is not an image")
    assert "artwork_not_an_image" in _codes(exc.value)


def test_all_problems_are_returned_together():
    """An editor should fix the image once, not three times."""
    from app.artwork import validate_artwork

    buffer = io.BytesIO()
    Image.effect_noise((900, 600), 120).convert("RGB").save(buffer, format="PNG")
    with pytest.raises(ApiException) as exc:
        validate_artwork("poster", buffer.getvalue())
    assert len(exc.value.errors) >= 2


def test_messages_avoid_jargon_and_em_dashes():
    from app.artwork import validate_artwork

    with pytest.raises(ApiException) as exc:
        validate_artwork("thumbnail", _read("thumb_tiny.jpg"))
    message = exc.value.errors[0].message
    assert "—" not in message
    assert "aspect ratio" not in message.lower()
    assert "640" in message and "360" in message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_artwork_validation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.artwork'`.

- [ ] **Step 3: Write `api/app/artwork.py`**

```python
import hashlib
import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

from app.errors import ApiError, ApiException
from app.reference import ArtworkSpec, reference

ASPECT_TOLERANCE = 0.01
DIMENSION_TOLERANCE = 0.10
_LABEL = {"poster": "poster", "banner": "banner", "thumbnail": "thumbnail"}


@dataclass(frozen=True)
class ArtworkMeta:
    width: int
    height: int
    bytes: int
    checksum: str
    content_type: str


def _orientation(width: int, height: int) -> str:
    if width > height:
        return "landscape"
    if height > width:
        return "portrait"
    return "square"


def _aspect_message(spec: ArtworkSpec, width: int, height: int) -> str:
    want = _orientation(spec.target_w, spec.target_h)
    got = _orientation(width, height)
    base = (
        f"Your {_LABEL[spec.kind]} is {width} by {height} pixels ({got}). "
        f"{_LABEL[spec.kind].capitalize()}s need to be {want}, "
        f"about {spec.target_w} by {spec.target_h}."
    )
    if got != want and {got, want} == {"portrait", "landscape"}:
        return base + " It looks like this image is rotated. Try the other orientation."
    return base


def _dimension_message(spec: ArtworkSpec, width: int, height: int) -> str:
    relation = "too small to look sharp on a TV" if width < spec.target_w else "larger than we need"
    return (
        f"This {_LABEL[spec.kind]} is {width} by {height} pixels, which is {relation}. "
        f"Please export it at about {spec.target_w} by {spec.target_h}."
    )


def validate_artwork(kind: str, data: bytes) -> ArtworkMeta:
    ref = reference()
    if kind not in ref.artwork_specs:
        raise ApiException(
            422,
            [
                ApiError(
                    "artwork_unknown_kind",
                    f"'{kind}' is not an artwork slot. "
                    f"Choose one of: {', '.join(sorted(ref.artwork_specs))}.",
                    "kind",
                )
            ],
        )
    spec = ref.artwork_specs[kind]

    try:
        image = Image.open(io.BytesIO(data))
        image.verify()
        image = Image.open(io.BytesIO(data))
        width, height = image.size
        image_format = (image.format or "").upper()
    except (UnidentifiedImageError, OSError) as exc:
        raise ApiException(
            422,
            [
                ApiError(
                    "artwork_not_an_image",
                    "We could not read that file as an image. "
                    "Please upload a JPG, PNG or WebP.",
                    "file",
                )
            ],
        ) from exc

    errors: list[ApiError] = []

    actual_aspect = width / height
    if abs(actual_aspect - spec.aspect) / spec.aspect > ASPECT_TOLERANCE:
        errors.append(
            ApiError("artwork_wrong_aspect", _aspect_message(spec, width, height), "file")
        )

    width_off = abs(width - spec.target_w) / spec.target_w > DIMENSION_TOLERANCE
    height_off = abs(height - spec.target_h) / spec.target_h > DIMENSION_TOLERANCE
    if width_off or height_off:
        errors.append(
            ApiError("artwork_wrong_dimensions", _dimension_message(spec, width, height), "file")
        )

    size_kb = len(data) / 1024
    if size_kb > spec.max_kb:
        errors.append(
            ApiError(
                "artwork_too_large",
                f"This file is {size_kb:.0f} KB. Artwork needs to be under {spec.max_kb} KB "
                "so pages load quickly for children on slow connections. "
                "Try exporting as JPEG at 80% quality.",
                "file",
            )
        )

    if errors:
        raise ApiException(422, errors)

    content_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(
        image_format, "application/octet-stream"
    )
    return ArtworkMeta(
        width=width,
        height=height,
        bytes=len(data),
        checksum=hashlib.sha256(data).hexdigest(),
        content_type=content_type,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_artwork_validation.py -v && ruff check .`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add api/app/artwork.py api/tests/test_artwork_validation.py
git commit -m "feat(api): artwork validation with editor-readable errors"
```

---

### Task 6: Artwork upload endpoint

**Files:**
- Create: `api/app/routers/artwork.py`
- Modify: `api/app/main.py`
- Test: `api/tests/test_artwork_upload.py`

**Interfaces:**
- Consumes: `validate_artwork`, `ArtworkMeta` from Task 5; `get_storage` from Task 4; `require_editor` from Task 3; `Artwork`, `Show`, `Episode` from Task 2
- Produces: `POST /admin/artwork`, `DELETE /admin/artwork/{artwork_id}`; response shape `{"id": int, "kind": str, "url": str, "width": int, "height": int, "bytes": int}`

- [ ] **Step 1: Write the failing test**

`api/tests/test_artwork_upload.py`:

```python
from pathlib import Path

from app.config import settings
from app.models import Season, Show

ASSETS = Path(settings.data_dir) / "assets"


def _make_show(db) -> Show:
    show = Show(slug="s", title="S", synopsis="", section="series", categories=["music"])
    db.add(show)
    db.flush()
    db.add(Season(show_id=show.id, season_number=1))
    db.flush()
    return show


def _upload(api, headers, kind, filename, show_id):
    return api.post(
        "/admin/artwork",
        headers=headers,
        data={"kind": kind, "show_id": str(show_id)},
        files={"file": (filename, (ASSETS / filename).read_bytes(), "image/jpeg")},
    )


def test_upload_good_poster_creates_a_record(api, db, editor_headers, tmp_path, monkeypatch):
    from app.storage import LocalDiskStorage
    from app.routers import artwork as artwork_router

    monkeypatch.setattr(
        artwork_router, "get_storage", lambda: LocalDiskStorage(tmp_path, "http://t/media")
    )
    show = _make_show(db)
    response = _upload(api, editor_headers, "poster", "poster_good.jpg", show.id)
    assert response.status_code == 201
    body = response.json()
    assert body["width"] == 600 and body["height"] == 900
    assert body["url"].startswith("http://t/media/")

    from app.models import Artwork

    assert db.query(Artwork).filter_by(show_id=show.id, kind="poster").count() == 1


def test_rejected_upload_writes_nothing_to_storage(
    api, db, editor_headers, tmp_path, monkeypatch
):
    """Validation runs before storage is touched, so a rejection leaves no orphan."""
    from app.storage import LocalDiskStorage
    from app.routers import artwork as artwork_router

    monkeypatch.setattr(
        artwork_router, "get_storage", lambda: LocalDiskStorage(tmp_path, "http://t/media")
    )
    show = _make_show(db)
    response = _upload(api, editor_headers, "poster", "poster_wrong_ratio.jpg", show.id)
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "artwork_wrong_aspect"
    assert list(tmp_path.rglob("*.jpg")) == []

    from app.models import Artwork

    assert db.query(Artwork).count() == 0


def test_upload_requires_authentication(api, db):
    show = _make_show(db)
    response = api.post(
        "/admin/artwork",
        data={"kind": "poster", "show_id": str(show.id)},
        files={"file": ("p.jpg", (ASSETS / "poster_good.jpg").read_bytes(), "image/jpeg")},
    )
    assert response.status_code == 401


def test_upload_requires_exactly_one_owner(api, editor_headers):
    response = api.post(
        "/admin/artwork",
        headers=editor_headers,
        data={"kind": "poster"},
        files={"file": ("p.jpg", (ASSETS / "poster_good.jpg").read_bytes(), "image/jpeg")},
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "artwork_missing_owner"


def test_uploading_the_same_kind_twice_replaces_it(
    api, db, editor_headers, tmp_path, monkeypatch
):
    from app.storage import LocalDiskStorage
    from app.routers import artwork as artwork_router

    monkeypatch.setattr(
        artwork_router, "get_storage", lambda: LocalDiskStorage(tmp_path, "http://t/media")
    )
    show = _make_show(db)
    _upload(api, editor_headers, "poster", "poster_good.jpg", show.id)
    second = _upload(api, editor_headers, "poster", "poster_good.jpg", show.id)
    assert second.status_code == 201

    from app.models import Artwork

    assert db.query(Artwork).filter_by(show_id=show.id, kind="poster").count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_artwork_upload.py -v`
Expected: FAIL with 404 on `/admin/artwork`, because the router does not exist.

- [ ] **Step 3: Write `api/app/routers/artwork.py`**

Replacing an existing slot rather than erroring is deliberate: an editor re-uploading a corrected image is the common case, and making them delete first is a step that buys nothing.

```python
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.artwork import validate_artwork
from app.auth import require_editor
from app.db import get_session
from app.errors import ApiError, ApiException
from app.models import Artwork, Episode, Show, User
from app.storage import get_storage

router = APIRouter(prefix="/admin/artwork", tags=["artwork"])


@router.post("", status_code=201)
async def upload_artwork(
    kind: str = Form(...),
    show_id: int | None = Form(None),
    episode_id: int | None = Form(None),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> dict:
    if (show_id is None) == (episode_id is None):
        raise ApiException(
            422,
            [
                ApiError(
                    "artwork_missing_owner",
                    "Choose whether this image belongs to a show or to an episode.",
                )
            ],
        )

    owner = session.get(Show, show_id) if show_id else session.get(Episode, episode_id)
    if owner is None:
        raise ApiException(
            404,
            [ApiError("not_found", "We could not find the show or episode for this image.")],
        )

    data = await file.read()
    # Validation first, so a rejected upload never leaves a file behind.
    meta = validate_artwork(kind, data)

    owner_folder = f"shows/{show_id}" if show_id else f"episodes/{episode_id}"
    extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[meta.content_type]
    key = f"artwork/{owner_folder}/{kind}-{meta.checksum[:12]}.{extension}"
    url = get_storage().put(key, data, meta.content_type)

    existing = session.scalar(
        select(Artwork).where(
            Artwork.kind == kind,
            Artwork.show_id == show_id,
            Artwork.episode_id == episode_id,
        )
    )
    if existing is not None:
        session.delete(existing)
        session.flush()

    record = Artwork(
        show_id=show_id,
        episode_id=episode_id,
        kind=kind,
        storage_key=key,
        width=meta.width,
        height=meta.height,
        bytes=meta.bytes,
        checksum=meta.checksum,
    )
    session.add(record)
    session.flush()
    return {
        "id": record.id,
        "kind": kind,
        "url": url,
        "width": meta.width,
        "height": meta.height,
        "bytes": meta.bytes,
    }


@router.delete("/{artwork_id}", status_code=204)
def delete_artwork(
    artwork_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> None:
    record = session.get(Artwork, artwork_id)
    if record is None:
        raise ApiException(404, [ApiError("not_found", "That image no longer exists.")])
    get_storage().delete(record.storage_key)
    session.delete(record)
    session.flush()
```

- [ ] **Step 4: Register the router and mount local media in `api/app/main.py`**

```python
from fastapi.staticfiles import StaticFiles

from app.routers import artwork, auth, health

app.include_router(artwork.router)

if settings.storage_backend == "local":
    settings.storage_local_root.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.storage_local_root), name="media")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd api && python -m pytest tests -v && ruff check .`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add api/app/routers/artwork.py api/app/main.py api/tests/test_artwork_upload.py
git commit -m "feat(api): artwork upload endpoint, validated before storage"
```

---

### Task 7: Content CRUD with write-time validation

**Files:**
- Create: `api/app/schemas.py`, `api/app/routers/shows.py`, `api/app/routers/episodes.py`
- Modify: `api/app/main.py`
- Test: `api/tests/test_content_crud.py`

**Interfaces:**
- Consumes: everything from Tasks 2 and 3
- Produces: `assert_publishable_episode(session, episode)` and `assert_publishable_show(session, show)` from `app.validation` (created here, extended in Task 8); routes `GET/POST /admin/shows`, `GET/PATCH/DELETE /admin/shows/{id}`, `POST /admin/shows/{id}/seasons`, `GET/POST /admin/episodes`, `GET/PATCH/DELETE /admin/episodes/{id}`; list response shape `{"items": [...], "total": int, "page": int, "page_size": int}`

- [ ] **Step 1: Write the failing test**

`api/tests/test_content_crud.py`:

```python
import pytest

from app.models import ArtworkKind, ContentStatus, Episode, Season, Show


@pytest.fixture
def show(db):
    record = Show(slug="alpha", title="Alpha", synopsis="", section="series", categories=["music"])
    db.add(record)
    db.flush()
    db.add(Season(show_id=record.id, season_number=1))
    db.flush()
    return record


def _add_thumbnail(db, episode_id):
    from app.models import Artwork

    db.add(
        Artwork(
            episode_id=episode_id,
            kind=ArtworkKind.thumbnail,
            storage_key="k",
            width=640,
            height=360,
            bytes=1000,
            checksum="c",
        )
    )
    db.flush()


def test_create_show_requires_auth(api):
    assert api.post("/admin/shows", json={"slug": "x", "title": "X"}).status_code == 401


def test_create_and_list_shows(api, editor_headers):
    created = api.post(
        "/admin/shows",
        headers=editor_headers,
        json={"slug": "beta", "title": "Beta", "section": "songs", "categories": ["music"]},
    )
    assert created.status_code == 201
    listed = api.get("/admin/shows", headers=editor_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_unknown_section_is_rejected_with_the_allowed_list(api, editor_headers):
    response = api.post(
        "/admin/shows",
        headers=editor_headers,
        json={"slug": "g", "title": "G", "section": "cartoons"},
    )
    assert response.status_code == 422
    error = response.json()["errors"][0]
    assert error["code"] == "unknown_section"
    assert "featured" in error["message"]


def test_publishing_a_show_without_a_section_is_refused(api, editor_headers, db, show):
    show.section = None
    db.flush()
    response = api.patch(
        f"/admin/shows/{show.id}", headers=editor_headers, json={"status": "published"}
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "show_missing_section"


def test_publishing_an_episode_without_artwork_is_refused(api, editor_headers, db, show):
    episode = Episode(
        season_id=show.seasons[0].id,
        episode_number=1,
        title="E1",
        duration_seconds=300,
        language="en",
        content_group="alpha-s01e01",
    )
    db.add(episode)
    db.flush()
    response = api.patch(
        f"/admin/episodes/{episode.id}", headers=editor_headers, json={"status": "published"}
    )
    assert response.status_code == 422
    codes = {e["code"] for e in response.json()["errors"]}
    assert "episode_missing_artwork" in codes


def test_publishing_an_episode_without_duration_is_refused(api, editor_headers, db, show):
    episode = Episode(
        season_id=show.seasons[0].id,
        episode_number=2,
        title="E2",
        duration_seconds=None,
        language="en",
        content_group="alpha-s01e02",
    )
    db.add(episode)
    db.flush()
    _add_thumbnail(db, episode.id)
    response = api.patch(
        f"/admin/episodes/{episode.id}", headers=editor_headers, json={"status": "published"}
    )
    assert response.status_code == 422
    assert "episode_missing_duration" in {e["code"] for e in response.json()["errors"]}


def test_publishing_a_complete_episode_succeeds(api, editor_headers, db, show):
    episode = Episode(
        season_id=show.seasons[0].id,
        episode_number=3,
        title="E3",
        duration_seconds=300,
        language="en",
        content_group="alpha-s01e03",
    )
    db.add(episode)
    db.flush()
    _add_thumbnail(db, episode.id)
    response = api.patch(
        f"/admin/episodes/{episode.id}", headers=editor_headers, json={"status": "published"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "published"


def test_duplicate_content_group_and_language_is_a_readable_conflict(api, editor_headers, db, show):
    body = {
        "season_id": show.seasons[0].id,
        "episode_number": 9,
        "title": "Dup",
        "duration_seconds": 300,
        "language": "hi",
        "content_group": "alpha-s01e09",
    }
    assert api.post("/admin/episodes", headers=editor_headers, json=body).status_code == 201
    second = api.post("/admin/episodes", headers=editor_headers, json={**body, "episode_number": 10})
    assert second.status_code == 409
    error = second.json()["errors"][0]
    assert error["code"] == "duplicate_language_variant"
    assert "hi" in error["message"]


def test_show_list_filters_compose(api, editor_headers, db):
    db.add_all(
        [
            Show(slug="a", title="Aa", section="series", synopsis="", categories=["music"],
                 status=ContentStatus.published),
            Show(slug="b", title="Bb", section="songs", synopsis="", categories=["music"],
                 status=ContentStatus.draft),
        ]
    )
    db.flush()
    response = api.get(
        "/admin/shows?section=series&status=published", headers=editor_headers
    )
    assert response.status_code == 200
    assert [item["slug"] for item in response.json()["items"]] == ["a"]


def test_show_list_paginates(api, editor_headers, db):
    for i in range(25):
        db.add(Show(slug=f"s{i:02d}", title=f"S{i:02d}", synopsis="", categories=[]))
    db.flush()
    response = api.get("/admin/shows?page=2&page_size=10", headers=editor_headers)
    body = response.json()
    assert body["total"] == 25
    assert len(body["items"]) == 10
    assert body["page"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_content_crud.py -v`
Expected: FAIL, 404 on every route.

- [ ] **Step 3: Write `api/app/validation.py` with the write-time rules**

Task 8 extends this file with the full report. These two functions are the rules the report will reuse, so they live here from the start rather than being written twice.

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Artwork, ContentStatus, Episode, Season, Show
from app.reference import reference

TRAILER_SEASON = 0


def episode_publish_blockers(session: Session, episode: Episode) -> list[ApiError]:
    """Why this episode cannot be published. Empty list means it can."""
    errors: list[ApiError] = []
    if not episode.duration_seconds:
        errors.append(
            ApiError(
                "episode_missing_duration",
                f"'{episode.title}' has no duration yet. "
                "Add how long the episode runs before publishing it.",
                "duration_seconds",
            )
        )
    has_artwork = session.scalar(
        select(Artwork.id).where(Artwork.episode_id == episode.id).limit(1)
    )
    if has_artwork is None:
        errors.append(
            ApiError(
                "episode_missing_artwork",
                f"'{episode.title}' has no thumbnail yet. "
                "Upload a 640 by 360 image before publishing it.",
                "artwork",
            )
        )
    ref = reference()
    if episode.language not in ref.languages:
        errors.append(
            ApiError(
                "unknown_language",
                f"'{episode.language}' is not a language we ship. "
                f"Use one of: {', '.join(ref.languages)}.",
                "language",
            )
        )
    return errors


def show_publish_blockers(session: Session, show: Show) -> list[ApiError]:
    errors: list[ApiError] = []
    ref = reference()
    if not show.section:
        errors.append(
            ApiError(
                "show_missing_section",
                f"'{show.title}' has no section, so there is no row to put it in. "
                f"Choose one of: {', '.join(ref.sections)}.",
                "section",
            )
        )
    elif show.section not in ref.sections:
        errors.append(
            ApiError(
                "unknown_section",
                f"'{show.section}' is not a section we ship. "
                f"Choose one of: {', '.join(ref.sections)}.",
                "section",
            )
        )
    unknown = [c for c in (show.categories or []) if c not in ref.categories]
    if unknown:
        errors.append(
            ApiError(
                "unknown_category",
                f"These categories are not in our list: {', '.join(unknown)}. "
                f"Allowed: {', '.join(ref.categories)}.",
                "categories",
            )
        )
    published = session.scalar(
        select(Episode.id)
        .join(Season, Season.id == Episode.season_id)
        .where(
            Season.show_id == show.id,
            Season.season_number != TRAILER_SEASON,
            Episode.status == ContentStatus.published,
        )
        .limit(1)
    )
    if published is None:
        errors.append(
            ApiError(
                "show_no_published_episodes",
                f"'{show.title}' has no published episodes, so viewers would see an "
                "empty show. Publish at least one episode first.",
                "episodes",
            )
        )
    return errors
```

- [ ] **Step 4: Write `api/app/schemas.py`**

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ShowCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=255)
    synopsis: str = ""
    section: str | None = None
    categories: list[str] = Field(default_factory=list)


class ShowUpdate(BaseModel):
    title: str | None = None
    synopsis: str | None = None
    section: str | None = None
    categories: list[str] | None = None
    status: str | None = None


class ShowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    synopsis: str
    section: str | None
    categories: list[str]
    status: str
    updated_at: datetime


class SeasonCreate(BaseModel):
    season_number: int = Field(ge=0)


class EpisodeCreate(BaseModel):
    season_id: int
    episode_number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=255)
    duration_seconds: int | None = Field(default=None, ge=1)
    language: str
    content_group: str = Field(min_length=1, max_length=160)


class EpisodeUpdate(BaseModel):
    episode_number: int | None = Field(default=None, ge=1)
    title: str | None = None
    duration_seconds: int | None = Field(default=None, ge=1)
    language: str | None = None
    content_group: str | None = None
    status: str | None = None


class EpisodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season_id: int
    episode_number: int
    title: str
    duration_seconds: int | None
    language: str
    content_group: str
    status: str


class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
```

- [ ] **Step 5: Write `api/app/routers/shows.py`**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import require_editor
from app.db import get_session
from app.errors import ApiError, ApiException
from app.models import ContentStatus, Season, Show, User
from app.reference import reference
from app.schemas import Page, SeasonCreate, ShowCreate, ShowOut, ShowUpdate
from app.validation import show_publish_blockers

router = APIRouter(prefix="/admin/shows", tags=["shows"])


def _check_vocabulary(section: str | None, categories: list[str] | None) -> None:
    ref = reference()
    errors: list[ApiError] = []
    if section is not None and section not in ref.sections:
        errors.append(
            ApiError(
                "unknown_section",
                f"'{section}' is not a section we ship. Choose one of: "
                f"{', '.join(ref.sections)}.",
                "section",
            )
        )
    unknown = [c for c in (categories or []) if c not in ref.categories]
    if unknown:
        errors.append(
            ApiError(
                "unknown_category",
                f"These categories are not in our list: {', '.join(unknown)}. "
                f"Allowed: {', '.join(ref.categories)}.",
                "categories",
            )
        )
    if errors:
        raise ApiException(422, errors)


@router.get("", response_model=Page)
def list_shows(
    q: str | None = None,
    section: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> Page:
    query = select(Show)
    if q:
        pattern = f"%{q}%"
        query = query.where(or_(Show.title.ilike(pattern), Show.slug.ilike(pattern)))
    if section:
        query = query.where(Show.section == section)
    if status:
        query = query.where(Show.status == status)

    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(Show.title, Show.slug).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Page(
        items=[ShowOut.model_validate(r).model_dump(mode="json") for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ShowOut, status_code=201)
def create_show(
    body: ShowCreate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> Show:
    _check_vocabulary(body.section, body.categories)
    if session.scalar(select(Show.id).where(Show.slug == body.slug)):
        raise ApiException(
            409,
            [
                ApiError(
                    "duplicate_slug",
                    f"A show with the web address '{body.slug}' already exists. "
                    "Pick a different one.",
                    "slug",
                )
            ],
        )
    show = Show(**body.model_dump())
    session.add(show)
    session.flush()
    return show


def _get_show(session: Session, show_id: int) -> Show:
    show = session.get(Show, show_id)
    if show is None:
        raise ApiException(404, [ApiError("not_found", "We could not find that show.")])
    return show


@router.get("/{show_id}", response_model=ShowOut)
def get_show(
    show_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> Show:
    return _get_show(session, show_id)


@router.patch("/{show_id}", response_model=ShowOut)
def update_show(
    show_id: int,
    body: ShowUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> Show:
    show = _get_show(session, show_id)
    fields = body.model_dump(exclude_unset=True)
    _check_vocabulary(fields.get("section"), fields.get("categories"))

    for key, value in fields.items():
        if key != "status":
            setattr(show, key, value)
    session.flush()

    if fields.get("status") == ContentStatus.published.value:
        blockers = show_publish_blockers(session, show)
        if blockers:
            raise ApiException(422, blockers)
        show.status = ContentStatus.published
    elif fields.get("status") == ContentStatus.draft.value:
        show.status = ContentStatus.draft
    session.flush()
    return show


@router.delete("/{show_id}", status_code=204)
def delete_show(
    show_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> None:
    session.delete(_get_show(session, show_id))
    session.flush()


@router.post("/{show_id}/seasons", status_code=201)
def create_season(
    show_id: int,
    body: SeasonCreate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> dict:
    _get_show(session, show_id)
    if session.scalar(
        select(Season.id).where(
            Season.show_id == show_id, Season.season_number == body.season_number
        )
    ):
        raise ApiException(
            409,
            [
                ApiError(
                    "duplicate_season",
                    f"Season {body.season_number} already exists for this show.",
                    "season_number",
                )
            ],
        )
    season = Season(show_id=show_id, season_number=body.season_number)
    session.add(season)
    session.flush()
    return {"id": season.id, "show_id": show_id, "season_number": season.season_number}
```

- [ ] **Step 6: Write `api/app/routers/episodes.py`**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_editor
from app.db import get_session
from app.errors import ApiError, ApiException
from app.models import ContentStatus, Episode, Season, User
from app.reference import reference
from app.schemas import EpisodeCreate, EpisodeOut, EpisodeUpdate, Page
from app.validation import episode_publish_blockers

router = APIRouter(prefix="/admin/episodes", tags=["episodes"])


def _duplicate_variant_error(content_group: str, language: str) -> ApiException:
    return ApiException(
        409,
        [
            ApiError(
                "duplicate_language_variant",
                f"There is already a '{language}' version of this episode "
                f"(group '{content_group}'). Each language may appear once per episode. "
                "Edit the existing one instead of adding a second.",
                "language",
            )
        ],
    )


def _assert_variant_is_free(
    session: Session, content_group: str, language: str, exclude_id: int | None = None
) -> None:
    query = select(Episode.id).where(
        Episode.content_group == content_group, Episode.language == language
    )
    if exclude_id is not None:
        query = query.where(Episode.id != exclude_id)
    if session.scalar(query):
        raise _duplicate_variant_error(content_group, language)


@router.get("", response_model=Page)
def list_episodes(
    q: str | None = None,
    show_id: int | None = None,
    season_id: int | None = None,
    status: str | None = None,
    language: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> Page:
    query = select(Episode).join(Season, Season.id == Episode.season_id)
    if q:
        query = query.where(Episode.title.ilike(f"%{q}%"))
    if show_id:
        query = query.where(Season.show_id == show_id)
    if season_id:
        query = query.where(Episode.season_id == season_id)
    if status:
        query = query.where(Episode.status == status)
    if language:
        query = query.where(Episode.language == language)

    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(Season.season_number, Episode.episode_number, Episode.language)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return Page(
        items=[EpisodeOut.model_validate(r).model_dump(mode="json") for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=EpisodeOut, status_code=201)
def create_episode(
    body: EpisodeCreate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> Episode:
    if session.get(Season, body.season_id) is None:
        raise ApiException(404, [ApiError("not_found", "We could not find that season.")])
    ref = reference()
    if body.language not in ref.languages:
        raise ApiException(
            422,
            [
                ApiError(
                    "unknown_language",
                    f"'{body.language}' is not a language we ship. "
                    f"Use one of: {', '.join(ref.languages)}.",
                    "language",
                )
            ],
        )
    _assert_variant_is_free(session, body.content_group, body.language)
    episode = Episode(**body.model_dump())
    session.add(episode)
    session.flush()
    return episode


def _get_episode(session: Session, episode_id: int) -> Episode:
    episode = session.get(Episode, episode_id)
    if episode is None:
        raise ApiException(404, [ApiError("not_found", "We could not find that episode.")])
    return episode


@router.get("/{episode_id}", response_model=EpisodeOut)
def get_episode(
    episode_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> Episode:
    return _get_episode(session, episode_id)


@router.patch("/{episode_id}", response_model=EpisodeOut)
def update_episode(
    episode_id: int,
    body: EpisodeUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> Episode:
    episode = _get_episode(session, episode_id)
    fields = body.model_dump(exclude_unset=True)

    group = fields.get("content_group", episode.content_group)
    language = fields.get("language", episode.language)
    if group != episode.content_group or language != episode.language:
        _assert_variant_is_free(session, group, language, exclude_id=episode.id)

    for key, value in fields.items():
        if key != "status":
            setattr(episode, key, value)
    session.flush()

    if fields.get("status") == ContentStatus.published.value:
        blockers = episode_publish_blockers(session, episode)
        if blockers:
            raise ApiException(422, blockers)
        episode.status = ContentStatus.published
    elif fields.get("status") == ContentStatus.draft.value:
        episode.status = ContentStatus.draft
    session.flush()
    return episode


@router.delete("/{episode_id}", status_code=204)
def delete_episode(
    episode_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> None:
    session.delete(_get_episode(session, episode_id))
    session.flush()
```

- [ ] **Step 7: Register both routers in `api/app/main.py`**

```python
from app.routers import artwork, auth, episodes, health, shows

app.include_router(shows.router)
app.include_router(episodes.router)
```

- [ ] **Step 8: Run test to verify it passes**

Run: `cd api && python -m pytest tests -v && ruff check .`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add api/app/schemas.py api/app/validation.py api/app/routers api/app/main.py api/tests
git commit -m "feat(api): show and episode CRUD with write-time publish validation"
```

---
