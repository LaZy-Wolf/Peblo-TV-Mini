"""Read path.

The catalogue a run produced never changes, so caching it by run id is safe
forever. Only the pointer moves, and re-reading that is one indexed lookup on
a short TTL rather than a database round trip per request.
"""

import json
import time

from sqlalchemy.orm import Session

from app.models import CatalogPointer, PublishRun
from app.storage.base import ObjectNotFound, Storage

POINTER_TTL_SECONDS = 5

_pointer_cache: tuple[float, str | None] = (0.0, None)
_catalog_cache: dict[str, dict] = {}


def invalidate_cache() -> None:
    """Called after a publish or rollback, so a change is visible at once."""
    global _pointer_cache
    _pointer_cache = (0.0, None)
    _catalog_cache.clear()


def _current_key(session: Session) -> str | None:
    global _pointer_cache
    cached_at, key = _pointer_cache
    if cached_at and time.monotonic() - cached_at < POINTER_TTL_SECONDS:
        return key

    pointer = session.get(CatalogPointer, 1)
    run = None
    if pointer is not None and pointer.current_run_id is not None:
        run = session.get(PublishRun, pointer.current_run_id)
    key = run.catalog_key if run else None
    _pointer_cache = (time.monotonic(), key)
    return key


def current_catalog(session: Session, storage: Storage) -> dict | None:
    key = _current_key(session)
    if key is None:
        return None
    if key in _catalog_cache:
        return _catalog_cache[key]
    try:
        catalog = json.loads(storage.get(key))
    except ObjectNotFound:
        return None
    _catalog_cache[key] = catalog
    return catalog
