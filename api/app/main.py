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
from app.routers import admin_catalog, artwork, auth, episodes, health, shows

app = FastAPI(title="Peblo TV Mini API")
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

if settings.storage_backend == "local":
    # Serves uploaded artwork in development. In production R2 serves these
    # directly and this mount is never reached.
    settings.storage_local_root.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.storage_local_root), name="media")
