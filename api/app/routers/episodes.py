from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_editor
from app.db import get_session
from app.errors import ApiError, ApiException
from app.models import ContentStatus, Episode, Season, User
from app.reference import reference
from app.routers.shows import artwork_map
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


def _get_episode(session: Session, episode_id: int) -> Episode:
    episode = session.get(Episode, episode_id)
    if episode is None:
        raise ApiException(404, [ApiError("not_found", "We could not find that episode.")])
    return episode


@router.get("", response_model=Page)
def list_episodes(
    q: str | None = None,
    show_id: int | None = None,
    season_id: int | None = None,
    status: str | None = None,
    language: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
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


@router.post("", status_code=201)
def create_episode(
    body: EpisodeCreate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> dict:
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
    return {**EpisodeOut.model_validate(episode).model_dump(mode="json"), "artwork": {}}


@router.get("/{episode_id}")
def get_episode(
    episode_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> dict:
    episode = _get_episode(session, episode_id)
    return {
        **EpisodeOut.model_validate(episode).model_dump(mode="json"),
        "artwork": artwork_map(episode.artwork),
        "season_number": episode.season.season_number,
        "show_id": episode.season.show_id,
        "show_title": episode.season.show.title,
    }


@router.patch("/{episode_id}")
def update_episode(
    episode_id: int,
    body: EpisodeUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> dict:
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

    if fields.get("status") == ContentStatus.published:
        blockers = episode_publish_blockers(session, episode)
        if blockers:
            raise ApiException(422, blockers)
        episode.status = ContentStatus.published
    elif fields.get("status") == ContentStatus.draft:
        episode.status = ContentStatus.draft
    session.flush()
    return {
        **EpisodeOut.model_validate(episode).model_dump(mode="json"),
        "artwork": artwork_map(episode.artwork),
        "season_number": episode.season.season_number,
        "show_id": episode.season.show_id,
        "show_title": episode.season.show.title,
    }


@router.delete("/{episode_id}", status_code=204)
def delete_episode(
    episode_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> None:
    session.delete(_get_episode(session, episode_id))
    session.flush()
