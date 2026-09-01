from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Artwork, ContentStatus, Episode, Season, Show
from app.reference import reference

TRAILER_SEASON = 0


def episode_publish_blockers(session: Session, episode: Episode) -> list[ApiError]:
    """Why this episode cannot be published. An empty list means it can."""
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
    """Why this show cannot be published. An empty list means it can."""
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
                f"'{show.title}' has no published episodes, so viewers would see an empty "
                "show. Publish at least one episode first.",
                "episodes",
            )
        )
    return errors
