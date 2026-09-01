from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

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


DURATION_MISMATCH_RATIO = 0.20


@dataclass
class Issue:
    code: str
    message: str
    fix_hint: str
    entity_type: str
    entity_id: int | None
    entity_label: str


@dataclass
class ShowGroup:
    show_id: int | None
    show_title: str
    show_slug: str
    blocking: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)


@dataclass
class ValidationReport:
    can_publish: bool
    blocking_count: int
    warning_count: int
    groups: list[ShowGroup]
    import_problems: list[dict]


def _as_issue(
    error: ApiError, hint: str, entity_type: str, entity_id: int | None, label: str
) -> Issue:
    return Issue(
        code=error.code,
        message=error.message,
        fix_hint=hint,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=label,
    )


def _show_artwork_warning(show: Show) -> Issue | None:
    missing = {"poster", "banner"} - {a.kind for a in show.artwork}
    if not missing:
        return None
    return Issue(
        code="show_missing_artwork",
        message=(
            f"'{show.title}' has no {' or '.join(sorted(missing))}. "
            "Rows and the featured banner will fall back to a plain card."
        ),
        fix_hint="Upload the missing image on the show page.",
        entity_type="show",
        entity_id=show.id,
        entity_label=show.title,
    )


def _trailer_issues(show: Show, episode: Episode) -> list[tuple[str, Issue]]:
    """Trailers need a thumbnail only. See decision D4 in the design spec."""
    kinds = {a.kind for a in episode.artwork}
    # The seed titles trailers "Trailer", so prefixing would read "Trailer: Trailer".
    label = episode.title if "trailer" in episode.title.lower() else f"Trailer: {episode.title}"
    if "thumbnail" not in kinds:
        return [
            (
                "blocking",
                Issue(
                    code="trailer_missing_thumbnail",
                    message=(
                        f"The trailer for '{show.title}' has no thumbnail. "
                        "Upload a 640 by 360 image."
                    ),
                    fix_hint="Trailers need a thumbnail and nothing else.",
                    entity_type="episode",
                    entity_id=episode.id,
                    entity_label=label,
                ),
            )
        ]
    if not {"poster", "banner"} & kinds:
        return [
            (
                "warning",
                Issue(
                    code="trailer_thumbnail_only",
                    message=(
                        f"The trailer for '{show.title}' has a thumbnail only. That is fine, "
                        "trailers never appear in poster rows."
                    ),
                    fix_hint="No action needed.",
                    entity_type="episode",
                    entity_id=episode.id,
                    entity_label=label,
                ),
            )
        ]
    return []


def _duration_warning(content_group: str, variants: list[Episode]) -> Issue | None:
    durations = [e.duration_seconds for e in variants if e.duration_seconds]
    if len(durations) < 2:
        return None
    shortest, longest = min(durations), max(durations)
    if (longest - shortest) / longest <= DURATION_MISMATCH_RATIO:
        return None
    languages = ", ".join(sorted(e.language for e in variants))
    return Issue(
        code="variant_duration_mismatch",
        message=(
            f"The {languages} versions of '{variants[0].title}' run {shortest} and "
            f"{longest} seconds. Viewers see the first language's duration. Check that "
            "one of them is not the wrong file."
        ),
        fix_hint="Open each language version and confirm its duration.",
        entity_type="content_group",
        entity_id=None,
        entity_label=content_group,
    )


def build_validation_report(session: Session) -> ValidationReport:
    """Everything currently blocking a publish, grouped so an editor can act."""
    from app.models import ImportIssue

    groups: list[ShowGroup] = []
    shows = session.scalars(
        select(Show).options(selectinload(Show.seasons).selectinload(Season.episodes))
    ).all()

    for show in sorted(shows, key=lambda s: (s.title, s.slug)):
        group = ShowGroup(show_id=show.id, show_title=show.title, show_slug=show.slug)

        if show.status == ContentStatus.published:
            for error in show_publish_blockers(session, show):
                group.blocking.append(
                    _as_issue(
                        error,
                        "Open the show and fix this field, then try publishing again.",
                        "show",
                        show.id,
                        show.title,
                    )
                )
            warning = _show_artwork_warning(show)
            if warning is not None:
                group.warnings.append(warning)

        by_group: dict[str, list[Episode]] = defaultdict(list)
        for season in show.seasons:
            for episode in season.episodes:
                if episode.status != ContentStatus.published:
                    continue
                by_group[episode.content_group].append(episode)
                is_trailer = season.season_number == TRAILER_SEASON
                label = f"S{season.season_number}E{episode.episode_number} {episode.title}"

                for error in episode_publish_blockers(session, episode):
                    # A trailer's artwork is judged by the trailer rules below.
                    if is_trailer and error.code == "episode_missing_artwork":
                        continue
                    group.blocking.append(
                        _as_issue(
                            error,
                            "Open the episode and fix this, then try publishing again.",
                            "episode",
                            episode.id,
                            label,
                        )
                    )

                if is_trailer:
                    for severity, issue in _trailer_issues(show, episode):
                        target = group.blocking if severity == "blocking" else group.warnings
                        target.append(issue)

        for content_group, variants in sorted(by_group.items()):
            warning = _duration_warning(content_group, variants)
            if warning is not None:
                group.warnings.append(warning)

        if group.blocking or group.warnings:
            groups.append(group)

    import_problems = [
        {
            "id": issue.id,
            "reason": issue.reason,
            "action": issue.action,
            "source_row": issue.source_row,
        }
        for issue in session.scalars(select(ImportIssue).order_by(ImportIssue.id)).all()
    ]

    blocking_count = sum(len(g.blocking) for g in groups)
    return ValidationReport(
        can_publish=blocking_count == 0,
        blocking_count=blocking_count,
        warning_count=sum(len(g.warnings) for g in groups),
        groups=groups,
        import_problems=import_problems,
    )
