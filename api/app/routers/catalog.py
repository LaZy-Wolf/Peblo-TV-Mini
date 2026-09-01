from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.catalog.search import search_catalog
from app.catalog.serve import current_catalog
from app.db import get_session
from app.errors import ApiError, ApiException
from app.storage import get_storage

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _catalog(session: Session) -> dict:
    catalog = current_catalog(session, get_storage())
    if catalog is None:
        raise ApiException(
            503,
            [
                ApiError(
                    "catalog_not_published",
                    "Nothing has been published yet. Check back shortly.",
                )
            ],
        )
    return catalog


@router.get("")
def get_catalog(session: Session = Depends(get_session)) -> dict:
    """What the viewer reads. No authentication, by design."""
    return _catalog(session)


@router.get("/search")
def search(
    q: str | None = None,
    category: str | None = None,
    language: str | None = None,
    section: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    return search_catalog(_catalog(session), q, category, language, section)
