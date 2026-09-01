import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.errors import (
    ApiException,
    api_exception_handler,
    validation_exception_handler,
)
from app.routers import admin_catalog, artwork, auth, catalog, episodes, health, shows

logger = logging.getLogger("peblo")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Fail any publish run abandoned by a dead process.

    Without this, a publish that died mid-flight shows as permanently running
    in the CMS and nobody can tell the catalogue is silently stale.
    """
    from app.catalog.publish import sweep_stale_runs
    from app.db import SessionLocal

    session = SessionLocal()
    try:
        swept = sweep_stale_runs(session)
        session.commit()
        if swept:
            logger.warning("Marked %s interrupted publish run(s) as failed.", swept)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Startup sweep skipped: %s", exc)
    finally:
        session.close()
    yield


app = FastAPI(title="Peblo TV Mini API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(ApiException, api_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(artwork.router)
app.include_router(shows.router)
app.include_router(episodes.router)
app.include_router(admin_catalog.router)
app.include_router(catalog.router)

if settings.storage_backend == "local":
    # Serves uploaded artwork in development. In production R2 serves these
    # directly and this mount is never reached.
    settings.storage_local_root.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.storage_local_root), name="media")
