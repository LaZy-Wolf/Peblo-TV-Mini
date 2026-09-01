from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import require_editor
from app.db import get_session
from app.errors import ApiError, ApiException
from app.models import Artwork, ContentStatus, Season, Show, User
from app.reference import reference
from app.schemas import Page, SeasonCreate, ShowCreate, ShowOut, ShowUpdate
from app.storage import get_storage
from app.validation import show_publish_blockers

router = APIRouter(prefix="/admin/shows", tags=["shows"])


def artwork_map(records: list[Artwork]) -> dict[str, str]:
    storage = get_storage()
    return {a.kind: storage.url(a.storage_key) for a in records}


def _check_vocabulary(section: str | None, categories: list[str] | None) -> None:
    ref = reference()
    errors: list[ApiError] = []
    if section is not None and section not in ref.sections:
        errors.append(
            ApiError(
                "unknown_section",
                f"'{section}' is not a section we ship. "
                f"Choose one of: {', '.join(ref.sections)}.",
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


def _get_show(session: Session, show_id: int) -> Show:
    show = session.get(Show, show_id)
    if show is None:
        raise ApiException(404, [ApiError("not_found", "We could not find that show.")])
    return show


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


@router.post("", status_code=201)
def create_show(
    body: ShowCreate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> dict:
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
    return {**ShowOut.model_validate(show).model_dump(mode="json"), "artwork": {}}


@router.get("/{show_id}")
def get_show(
    show_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> dict:
    show = _get_show(session, show_id)
    return {
        **ShowOut.model_validate(show).model_dump(mode="json"),
        "artwork": artwork_map(show.artwork),
    }


@router.patch("/{show_id}")
def update_show(
    show_id: int,
    body: ShowUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> dict:
    show = _get_show(session, show_id)
    fields = body.model_dump(exclude_unset=True)
    _check_vocabulary(fields.get("section"), fields.get("categories"))

    for key, value in fields.items():
        if key != "status":
            setattr(show, key, value)
    session.flush()

    if fields.get("status") == ContentStatus.published:
        blockers = show_publish_blockers(session, show)
        if blockers:
            raise ApiException(422, blockers)
        show.status = ContentStatus.published
    elif fields.get("status") == ContentStatus.draft:
        show.status = ContentStatus.draft
    session.flush()
    return {
        **ShowOut.model_validate(show).model_dump(mode="json"),
        "artwork": artwork_map(show.artwork),
    }


@router.delete("/{show_id}", status_code=204)
def delete_show(
    show_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> None:
    session.delete(_get_show(session, show_id))
    session.flush()


@router.get("/{show_id}/seasons")
def list_seasons(
    show_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> dict:
    show = _get_show(session, show_id)
    seasons = sorted(show.seasons, key=lambda s: s.season_number)
    return {
        "items": [
            {"id": s.id, "show_id": show_id, "season_number": s.season_number} for s in seasons
        ]
    }


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
