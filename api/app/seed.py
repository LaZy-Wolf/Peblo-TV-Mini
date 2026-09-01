"""Loads the supplied seed_shows.json into the database.

The seed is a bulk import, so it can contain rows the API itself would have
refused. Rather than silently dropping those, this module applies the same
write-time rules the API applies and records what it had to do, so the
validation report can show an editor exactly what arrived broken.
"""

import json
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.artwork import validate_artwork
from app.auth import hash_password
from app.config import settings
from app.models import (
    Artwork,
    ContentStatus,
    Episode,
    ImportAction,
    ImportIssue,
    Role,
    Season,
    Show,
    User,
)
from app.storage.base import Storage

SHOW_ARTWORK = {
    "poster": "poster_good.jpg",
    "banner": "banner_good.jpg",
    "thumbnail": "thumb_good.jpg",
}
EPISODE_ARTWORK = {"thumbnail": "thumb_good.jpg"}


@dataclass
class SeedResult:
    shows: int = 0
    seasons: int = 0
    episodes: int = 0
    artwork: int = 0
    rejected: int = 0
    downgraded: int = 0

    def summary(self) -> str:
        rows = "row" if self.rejected == 1 else "rows"
        return (
            f"Seeded {self.shows} shows, {self.episodes} episodes, "
            f"{self.artwork} artwork records. "
            f"{self.rejected} {rows} rejected, {self.downgraded} downgraded to draft."
        )


def _upload(storage: Storage, kind: str, filename: str, folder: str) -> Artwork:
    """Pushes the file through the same validator the CMS upload uses.

    A broken validator therefore fails the seed loudly rather than quietly
    seeding artwork that the API would have refused.
    """
    data = (settings.data_dir / "assets" / filename).read_bytes()
    meta = validate_artwork(kind, data)
    key = f"artwork/{folder}/{kind}-{meta.checksum[:12]}.jpg"
    storage.put(key, data, meta.content_type)
    return Artwork(
        kind=kind,
        storage_key=key,
        width=meta.width,
        height=meta.height,
        bytes=meta.bytes,
        checksum=meta.checksum,
    )


def _seed_users(session: Session) -> None:
    wanted = [
        (settings.seed_editor_email, settings.seed_editor_password, Role.editor),
        (settings.seed_admin_email, settings.seed_admin_password, Role.admin),
    ]
    for email, password, role in wanted:
        if session.scalar(select(User).where(User.email == email)) is None:
            session.add(User(email=email, password_hash=hash_password(password), role=role))
    session.flush()


def _existing_counts(session: Session) -> SeedResult:
    return SeedResult(
        shows=session.query(Show).count(),
        seasons=session.query(Season).count(),
        episodes=session.query(Episode).count(),
        artwork=session.query(Artwork).count(),
        rejected=session.query(ImportIssue)
        .filter(ImportIssue.action == ImportAction.rejected)
        .count(),
        downgraded=session.query(ImportIssue)
        .filter(ImportIssue.action == ImportAction.downgraded_to_draft)
        .count(),
    )


def seed(session: Session, storage: Storage) -> SeedResult:
    _seed_users(session)

    if session.scalar(select(Show.id).limit(1)) is not None:
        # Already seeded. Idempotent by design so a container restart is safe.
        return _existing_counts(session)

    rows = json.loads((settings.data_dir / "seed_shows.json").read_text(encoding="utf-8"))
    result = SeedResult()

    by_slug: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_slug[row["slug"]].append(row)

    for slug, show_rows in by_slug.items():
        first = show_rows[0]
        # D10: a show is published when any of its episodes is.
        any_published = any(r["status"] == "published" for r in show_rows)
        show = Show(
            slug=slug,
            title=first["show_title"],
            synopsis=first["synopsis"],
            section=first["section"],
            categories=list(first["categories"] or []),
            status=ContentStatus.published if any_published else ContentStatus.draft,
        )
        session.add(show)
        session.flush()
        result.shows += 1

        for kind, filename in SHOW_ARTWORK.items():
            record = _upload(storage, kind, filename, f"shows/{show.id}")
            record.show_id = show.id
            session.add(record)
            result.artwork += 1

        seasons: dict[int, Season] = {}
        for number in sorted({r["season_number"] for r in show_rows}):
            season = Season(show_id=show.id, season_number=number)
            session.add(season)
            seasons[number] = season
            result.seasons += 1
        session.flush()

        seen_variants: set[tuple[str, str]] = set()
        ordered = sorted(show_rows, key=lambda r: (r["season_number"], r["episode_number"]))
        for row in ordered:
            variant = (row["content_group"], row["language"])
            if variant in seen_variants:
                session.add(
                    ImportIssue(
                        source_row=row,
                        reason=(
                            f"There is already a '{row['language']}' version of "
                            f"'{row['content_group']}'. Each language may appear once per "
                            "episode, so this row was not imported. Check which of the two "
                            "is correct and re-add it if needed."
                        ),
                        action=ImportAction.rejected,
                    )
                )
                result.rejected += 1
                continue
            seen_variants.add(variant)

            has_artwork = bool(row["artwork_available"])
            status = (
                ContentStatus.published
                if row["status"] == "published"
                else ContentStatus.draft
            )
            incomplete = not has_artwork or not row["duration_seconds"]
            if status == ContentStatus.published and incomplete:
                session.add(
                    ImportIssue(
                        source_row=row,
                        reason=(
                            f"'{row['episode_title']}' arrived marked published but has no "
                            "artwork, which we do not allow. It was imported as a draft. "
                            "Upload a 640 by 360 thumbnail, then publish it."
                        ),
                        action=ImportAction.downgraded_to_draft,
                    )
                )
                status = ContentStatus.draft
                result.downgraded += 1

            episode = Episode(
                season_id=seasons[row["season_number"]].id,
                episode_number=row["episode_number"],
                title=row["episode_title"],
                duration_seconds=row["duration_seconds"],
                language=row["language"],
                content_group=row["content_group"],
                status=status,
            )
            session.add(episode)
            session.flush()
            result.episodes += 1

            if has_artwork:
                for kind, filename in EPISODE_ARTWORK.items():
                    record = _upload(storage, kind, filename, f"episodes/{episode.id}")
                    record.episode_id = episode.id
                    session.add(record)
                    result.artwork += 1

    session.flush()
    return result


def main() -> None:
    from app.db import SessionLocal
    from app.storage import get_storage

    session = SessionLocal()
    try:
        result = seed(session, get_storage())
        session.commit()
        print(result.summary())
    finally:
        session.close()


if __name__ == "__main__":
    main()
