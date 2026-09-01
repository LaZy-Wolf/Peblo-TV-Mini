import hashlib
import json
import uuid
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Artwork, ContentStatus, Episode, Season, Show
from app.reference import reference
from app.storage import get_storage

CATALOG_VERSION = 1
TRAILER_SEASON = 0


def _artwork_map(records: list[Artwork]) -> dict[str, str]:
    storage = get_storage()
    return {a.kind: storage.url(a.storage_key) for a in records}


def _collapse(variants: list[Episode]) -> dict:
    """Language variants of one episode become a single catalogue entry.

    The canonical variant is the one whose language comes first in
    reference.json, so its title, duration and thumbnail represent the group.
    """
    ref = reference()
    ordered = sorted(variants, key=lambda e: ref.language_order(e.language))
    canonical = ordered[0]
    return {
        "content_group": canonical.content_group,
        "episode_number": canonical.episode_number,
        "title": canonical.title,
        "duration_seconds": canonical.duration_seconds,
        "languages": ref.sort_languages([e.language for e in ordered]),
        "artwork": _artwork_map(canonical.artwork),
    }


def build_catalog(session: Session, run_id: uuid.UUID) -> dict:
    """Build the published catalogue from the database.

    Ordering is fully deterministic, so two runs over identical data produce
    byte identical output and the content hash is stable.
    """
    ref = reference()
    shows = session.scalars(
        select(Show)
        .where(Show.status == ContentStatus.published)
        .options(
            selectinload(Show.artwork),
            selectinload(Show.seasons)
            .selectinload(Season.episodes)
            .selectinload(Episode.artwork),
        )
    ).all()

    sections: dict[str, list[dict]] = {key: [] for key in ref.sections}

    for show in shows:
        if show.section not in sections:
            continue

        seasons_out: list[dict] = []
        trailers_out: list[dict] = []
        languages: list[str] = []

        for season in sorted(show.seasons, key=lambda s: s.season_number):
            published = [e for e in season.episodes if e.status == ContentStatus.published]
            if not published:
                continue

            grouped: dict[str, list[Episode]] = defaultdict(list)
            for episode in published:
                grouped[episode.content_group].append(episode)
                languages.append(episode.language)

            entries = sorted(
                (_collapse(v) for v in grouped.values()),
                key=lambda e: (e["episode_number"], e["content_group"]),
            )
            if season.season_number == TRAILER_SEASON:
                trailers_out.extend(entries)
            else:
                seasons_out.append({"season_number": season.season_number, "episodes": entries})

        if not seasons_out:
            # Defence in depth. The validation report blocks this case already,
            # so reaching here means a rule and the builder have disagreed.
            continue

        sections[show.section].append(
            {
                "slug": show.slug,
                "title": show.title,
                "synopsis": show.synopsis,
                "categories": sorted(show.categories or []),
                "languages": ref.sort_languages(languages),
                "artwork": _artwork_map(show.artwork),
                "trailers": trailers_out,
                "seasons": seasons_out,
            }
        )

    ordered_sections = [
        {"key": key, "shows": sorted(sections[key], key=lambda s: (s["title"], s["slug"]))}
        for key in ref.sections
    ]

    featured = next((s["shows"] for s in ordered_sections if s["key"] == "featured"), [])
    hero_source = featured or next((s["shows"] for s in ordered_sections if s["shows"]), [])

    return {
        "version": CATALOG_VERSION,
        "run_id": str(run_id),
        "generated_at": datetime.now(UTC).isoformat(),
        "hero": {"slug": hero_source[0]["slug"]} if hero_source else None,
        "sections": ordered_sections,
    }


def serialise(catalog: dict) -> bytes:
    return json.dumps(catalog, sort_keys=True, separators=(",", ":")).encode("utf-8")


def content_hash(catalog: dict) -> str:
    """Hash of the catalogue's content only.

    run_id and generated_at are excluded, so publishing twice over unchanged
    data produces the same hash and the second run is recorded as no_change.
    """
    stable = {k: v for k, v in catalog.items() if k not in {"run_id", "generated_at"}}
    return hashlib.sha256(
        json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
