# Peblo TV Mini Backend Implementation Plan, Part 2

> Implementation plan, written before any code.

**Spec:** `docs/superpowers/specs/2026-09-01-peblo-tv-mini-design.md`

---

### Task 8: Validation report

**Files:**
- Modify: `api/app/validation.py`
- Create: `api/app/routers/admin_catalog.py`
- Modify: `api/app/main.py`
- Test: `api/tests/test_validation_report.py`

**Interfaces:**
- Consumes: `episode_publish_blockers`, `show_publish_blockers` from Task 7; `ImportIssue` from Task 2
- Produces: `build_validation_report(session) -> ValidationReport` from `app.validation`; dataclasses `Issue(code, message, fix_hint, entity_type, entity_id, entity_label)`, `ShowGroup(show_id, show_title, show_slug, blocking, warnings)`, `ValidationReport(can_publish, blocking_count, warning_count, groups, import_problems)`; route `GET /admin/validation-report`

- [ ] **Step 1: Write the failing test**

`api/tests/test_validation_report.py`:

```python
from app.models import (
    Artwork,
    ArtworkKind,
    ContentStatus,
    Episode,
    ImportAction,
    ImportIssue,
    Season,
    Show,
)


def _publishable_show(db, slug="ok", section="series"):
    show = Show(
        slug=slug,
        title=slug.upper(),
        synopsis="",
        section=section,
        categories=["music"],
        status=ContentStatus.published,
    )
    db.add(show)
    db.flush()
    season = Season(show_id=show.id, season_number=1)
    db.add(season)
    db.flush()
    episode = Episode(
        season_id=season.id,
        episode_number=1,
        title="E1",
        duration_seconds=300,
        language="en",
        content_group=f"{slug}-s01e01",
        status=ContentStatus.published,
    )
    db.add(episode)
    db.flush()
    db.add(
        Artwork(
            episode_id=episode.id,
            kind=ArtworkKind.thumbnail,
            storage_key="k",
            width=640,
            height=360,
            bytes=10,
            checksum="c",
        )
    )
    for kind, w, h in (("poster", 600, 900), ("banner", 1280, 720)):
        db.add(
            Artwork(
                show_id=show.id,
                kind=kind,
                storage_key=f"k-{kind}",
                width=w,
                height=h,
                bytes=10,
                checksum="c",
            )
        )
    db.flush()
    return show, season, episode


def test_clean_data_can_publish(api, db, editor_headers):
    _publishable_show(db)
    body = api.get("/admin/validation-report", headers=editor_headers).json()
    assert body["can_publish"] is True
    assert body["blocking_count"] == 0


def test_published_show_without_section_blocks(api, db, editor_headers):
    show, _, _ = _publishable_show(db)
    show.section = None
    db.flush()
    body = api.get("/admin/validation-report", headers=editor_headers).json()
    assert body["can_publish"] is False
    codes = {i["code"] for g in body["groups"] for i in g["blocking"]}
    assert "show_missing_section" in codes


def test_published_episode_without_artwork_blocks(api, db, editor_headers):
    _, _, episode = _publishable_show(db)
    for record in list(episode.artwork):
        db.delete(record)
    db.flush()
    body = api.get("/admin/validation-report", headers=editor_headers).json()
    codes = {i["code"] for g in body["groups"] for i in g["blocking"]}
    assert "episode_missing_artwork" in codes


def test_trailer_without_poster_warns_and_does_not_block(api, db, editor_headers):
    """Per decision D4: a trailer needs a thumbnail only."""
    show, _, _ = _publishable_show(db)
    season_zero = Season(show_id=show.id, season_number=0)
    db.add(season_zero)
    db.flush()
    trailer = Episode(
        season_id=season_zero.id,
        episode_number=1,
        title="Trailer",
        duration_seconds=75,
        language="en",
        content_group=f"{show.slug}-s00e01",
        status=ContentStatus.published,
    )
    db.add(trailer)
    db.flush()
    db.add(
        Artwork(
            episode_id=trailer.id,
            kind=ArtworkKind.thumbnail,
            storage_key="t",
            width=640,
            height=360,
            bytes=10,
            checksum="c",
        )
    )
    db.flush()
    body = api.get("/admin/validation-report", headers=editor_headers).json()
    assert body["can_publish"] is True
    warning_codes = {i["code"] for g in body["groups"] for i in g["warnings"]}
    assert "trailer_thumbnail_only" in warning_codes


def test_divergent_variant_durations_warn(api, db, editor_headers):
    show, season, episode = _publishable_show(db)
    hindi = Episode(
        season_id=season.id,
        episode_number=1,
        title="E1",
        duration_seconds=900,
        language="hi",
        content_group=episode.content_group,
        status=ContentStatus.published,
    )
    db.add(hindi)
    db.flush()
    db.add(
        Artwork(
            episode_id=hindi.id,
            kind=ArtworkKind.thumbnail,
            storage_key="k2",
            width=640,
            height=360,
            bytes=10,
            checksum="c",
        )
    )
    db.flush()
    body = api.get("/admin/validation-report", headers=editor_headers).json()
    warning_codes = {i["code"] for g in body["groups"] for i in g["warnings"]}
    assert "variant_duration_mismatch" in warning_codes
    assert body["can_publish"] is True


def test_import_problems_are_surfaced(api, db, editor_headers):
    db.add_all(
        [
            ImportIssue(
                source_row={"episode_id": "ep_9001"},
                reason="Duplicate Hindi version of motis-many-lives-s01e02.",
                action=ImportAction.rejected,
            ),
            ImportIssue(
                source_row={"episode_id": "ep_0036"},
                reason="Marked published but has no artwork.",
                action=ImportAction.downgraded_to_draft,
            ),
        ]
    )
    db.flush()
    body = api.get("/admin/validation-report", headers=editor_headers).json()
    assert len(body["import_problems"]) == 2
    assert {p["action"] for p in body["import_problems"]} == {
        "rejected",
        "downgraded_to_draft",
    }


def test_report_requires_authentication(api):
    assert api.get("/admin/validation-report").status_code == 401


def test_draft_show_with_no_section_does_not_block(api, db, editor_headers):
    """rhyme-rangers in the seed is all draft. A draft show missing a section
    is a future problem, not a current blocker."""
    db.add(Show(slug="draft-one", title="Draft One", synopsis="", section=None, categories=[]))
    db.flush()
    body = api.get("/admin/validation-report", headers=editor_headers).json()
    assert body["can_publish"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_validation_report.py -v`
Expected: FAIL, 404 on `/admin/validation-report`.

- [ ] **Step 3: Append the report builder to `api/app/validation.py`**

```python
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy.orm import selectinload

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


def _issue(error: ApiError, hint: str, entity_type: str, entity_id: int | None, label: str) -> Issue:
    return Issue(
        code=error.code,
        message=error.message,
        fix_hint=hint,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=label,
    )


def build_validation_report(session: Session) -> ValidationReport:
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
                    _issue(
                        error,
                        "Open the show and fix this field, then try publishing again.",
                        "show",
                        show.id,
                        show.title,
                    )
                )
            has_show_art = {
                a.kind.value if hasattr(a.kind, "value") else a.kind for a in show.artwork
            }
            missing = {"poster", "banner"} - has_show_art
            if missing:
                group.warnings.append(
                    Issue(
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
                )

        by_group: dict[str, list] = defaultdict(list)
        for season in show.seasons:
            for episode in season.episodes:
                if episode.status != ContentStatus.published:
                    continue
                by_group[episode.content_group].append(episode)

                for error in episode_publish_blockers(session, episode):
                    if (
                        season.season_number == TRAILER_SEASON
                        and error.code == "episode_missing_artwork"
                    ):
                        continue
                    group.blocking.append(
                        _issue(
                            error,
                            "Open the episode and fix this, then try publishing again.",
                            "episode",
                            episode.id,
                            f"S{season.season_number}E{episode.episode_number} {episode.title}",
                        )
                    )

                if season.season_number == TRAILER_SEASON:
                    kinds = {
                        a.kind.value if hasattr(a.kind, "value") else a.kind
                        for a in episode.artwork
                    }
                    if "thumbnail" not in kinds:
                        group.blocking.append(
                            Issue(
                                code="trailer_missing_thumbnail",
                                message=(
                                    f"The trailer for '{show.title}' has no thumbnail. "
                                    "Upload a 640 by 360 image."
                                ),
                                fix_hint="Trailers need a thumbnail, nothing else.",
                                entity_type="episode",
                                entity_id=episode.id,
                                entity_label=f"Trailer: {episode.title}",
                            )
                        )
                    elif not {"poster", "banner"} & kinds:
                        group.warnings.append(
                            Issue(
                                code="trailer_thumbnail_only",
                                message=(
                                    f"The trailer for '{show.title}' has a thumbnail only. "
                                    "That is fine, trailers do not appear in poster rows."
                                ),
                                fix_hint="No action needed.",
                                entity_type="episode",
                                entity_id=episode.id,
                                entity_label=f"Trailer: {episode.title}",
                            )
                        )

        for content_group, variants in sorted(by_group.items()):
            durations = [e.duration_seconds for e in variants if e.duration_seconds]
            if len(durations) > 1:
                shortest, longest = min(durations), max(durations)
                if (longest - shortest) / longest > DURATION_MISMATCH_RATIO:
                    languages = ", ".join(sorted(e.language for e in variants))
                    group.warnings.append(
                        Issue(
                            code="variant_duration_mismatch",
                            message=(
                                f"The {languages} versions of '{variants[0].title}' run "
                                f"{shortest} and {longest} seconds. Viewers see the "
                                "first language's duration. Check one of them is not the "
                                "wrong file."
                            ),
                            fix_hint="Open each language version and confirm its duration.",
                            entity_type="content_group",
                            entity_id=None,
                            entity_label=content_group,
                        )
                    )

        if group.blocking or group.warnings:
            groups.append(group)

    import_problems = [
        {
            "id": issue.id,
            "reason": issue.reason,
            "action": issue.action.value if hasattr(issue.action, "value") else issue.action,
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
```

- [ ] **Step 4: Create `api/app/routers/admin_catalog.py` with the report route**

Publish and rollback join this router in Tasks 11 and 13.

```python
from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_editor
from app.db import get_session
from app.models import User
from app.validation import build_validation_report

router = APIRouter(prefix="/admin", tags=["catalog-admin"])


@router.get("/validation-report")
def validation_report(
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> dict:
    return asdict(build_validation_report(session))
```

- [ ] **Step 5: Register the router in `api/app/main.py`**

```python
from app.routers import admin_catalog, artwork, auth, episodes, health, shows

app.include_router(admin_catalog.router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_validation_report.py -v && ruff check .`
Expected: 8 passed.

- [ ] **Step 7: Commit**

```bash
git add api/app/validation.py api/app/routers/admin_catalog.py api/app/main.py api/tests/test_validation_report.py
git commit -m "feat(api): validation report grouped by show with fix hints"
```

---

### Task 9: Seeder

**Files:**
- Create: `api/app/seed.py`
- Test: `api/tests/test_seed.py`

**Interfaces:**
- Consumes: all models; `validate_artwork` from Task 5; `get_storage` from Task 4; `hash_password` from Task 3
- Produces: `seed(session, storage) -> SeedResult` from `app.seed`; `SeedResult` dataclass with `shows: int`, `seasons: int`, `episodes: int`, `artwork: int`, `rejected: int`, `downgraded: int`; and `python -m app.seed` as a CLI entry point

- [ ] **Step 1: Write the failing test**

`api/tests/test_seed.py`:

```python
import pytest

from app.models import (
    ContentStatus,
    Episode,
    ImportAction,
    ImportIssue,
    Season,
    Show,
    User,
)


@pytest.fixture
def seeded(db, tmp_path):
    from app.seed import seed
    from app.storage import LocalDiskStorage

    result = seed(db, LocalDiskStorage(tmp_path, "http://t/media"))
    db.flush()
    return result


def test_seed_creates_eight_shows(seeded, db):
    assert db.query(Show).count() == 8


def test_duplicate_variant_row_is_rejected_not_imported(seeded, db):
    """ep_9001 is a second Hindi version of motis-many-lives-s01e02."""
    rejected = (
        db.query(ImportIssue).filter(ImportIssue.action == ImportAction.rejected).all()
    )
    assert len(rejected) == 1
    assert rejected[0].source_row["episode_id"] == "ep_9001"
    assert seeded.rejected == 1

    variants = (
        db.query(Episode).filter(Episode.content_group == "motis-many-lives-s01e02").all()
    )
    assert sorted(e.language for e in variants) == ["en", "hi"]


def test_published_row_without_artwork_is_downgraded(seeded, db):
    """ep_0036 arrives published with an empty artwork list. It cannot be
    published, so it is imported as draft and reported rather than dropped."""
    downgraded = (
        db.query(ImportIssue)
        .filter(ImportIssue.action == ImportAction.downgraded_to_draft)
        .all()
    )
    assert len(downgraded) == 1
    assert downgraded[0].source_row["episode_id"] == "ep_0036"

    episode = (
        db.query(Episode)
        .filter(Episode.content_group == "discover-india-with-moti-s01e04")
        .one()
    )
    assert episode.status == ContentStatus.draft
    assert episode.artwork == []


def test_show_status_is_derived_from_its_episodes(seeded, db):
    """Decision D10."""
    rhyme = db.query(Show).filter_by(slug="rhyme-rangers").one()
    assert rhyme.status == ContentStatus.draft
    assert rhyme.section is None

    nest = db.query(Show).filter_by(slug="number-nest").one()
    assert nest.status == ContentStatus.published


def test_season_zero_is_imported_as_a_season_row(seeded, db):
    moti = db.query(Show).filter_by(slug="motis-many-lives").one()
    assert sorted(s.season_number for s in moti.seasons) == [0, 1]


def test_lyrical_show_stays_separate(seeded, db):
    """Same episode titles as peblo-songs, different content groups.
    Nothing may merge them."""
    songs = db.query(Show).filter_by(slug="peblo-songs").one()
    lyrical = db.query(Show).filter_by(slug="peblo-songs-lyrical").one()
    assert songs.id != lyrical.id
    groups = {
        e.content_group
        for show in (songs, lyrical)
        for season in show.seasons
        for e in season.episodes
    }
    assert len(groups) == 20


def test_artwork_is_materialised_for_shows_and_episodes(seeded, db):
    from app.models import Artwork

    moti = db.query(Show).filter_by(slug="motis-many-lives").one()
    kinds = {a.kind.value if hasattr(a.kind, "value") else a.kind for a in moti.artwork}
    assert kinds == {"poster", "banner", "thumbnail"}
    assert db.query(Artwork).filter(Artwork.episode_id.isnot(None)).count() > 0


def test_seed_creates_both_accounts(seeded, db):
    roles = {u.role.value if hasattr(u.role, "value") else u.role for u in db.query(User).all()}
    assert roles == {"editor", "admin"}


def test_seed_is_idempotent(db, tmp_path):
    from app.seed import seed
    from app.storage import LocalDiskStorage

    storage = LocalDiskStorage(tmp_path, "http://t/media")
    seed(db, storage)
    db.flush()
    seed(db, storage)
    db.flush()
    assert db.query(Show).count() == 8
    assert db.query(Episode).count() == 94
    assert db.query(ImportIssue).count() == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_seed.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.seed'`.

- [ ] **Step 3: Write `api/app/seed.py`**

```python
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

TRAILER_SEASON = 0
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


def _upload(storage: Storage, kind: str, filename: str, folder: str) -> Artwork:
    """Pushes the file through the same validator the CMS upload uses, so a
    broken validator fails the seed loudly instead of quietly seeding junk."""
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


def seed(session: Session, storage: Storage) -> SeedResult:
    result = SeedResult()
    _seed_users(session)

    if session.scalar(select(Show.id).limit(1)) is not None:
        # Already seeded. Idempotent by design so a container restart is safe.
        result.shows = session.query(Show).count()
        result.episodes = session.query(Episode).count()
        result.rejected = (
            session.query(ImportIssue).filter(ImportIssue.action == ImportAction.rejected).count()
        )
        result.downgraded = (
            session.query(ImportIssue)
            .filter(ImportIssue.action == ImportAction.downgraded_to_draft)
            .count()
        )
        return result

    rows = json.loads((settings.data_dir / "seed_shows.json").read_text(encoding="utf-8"))

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
        for row in sorted(show_rows, key=lambda r: (r["season_number"], r["episode_number"])):
            key = (row["content_group"], row["language"])
            if key in seen_variants:
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
            seen_variants.add(key)

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
        print(
            f"Seeded {result.shows} shows, {result.episodes} episodes, "
            f"{result.artwork} artwork records. "
            f"{result.rejected} rows rejected, {result.downgraded} downgraded to draft."
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_seed.py -v && ruff check .`
Expected: 9 passed. The 94 episode count in the idempotency test is 95 supplied rows minus the one rejected duplicate.

- [ ] **Step 5: Commit**

```bash
git add api/app/seed.py api/tests/test_seed.py
git commit -m "feat(api): seeder that reports rejected and downgraded rows"
```

---

### Task 10: Catalogue build

**Files:**
- Create: `api/app/catalog/__init__.py`, `api/app/catalog/build.py`
- Test: `api/tests/test_catalog_build.py`

**Interfaces:**
- Consumes: all models; `reference()` from Task 1
- Produces: `build_catalog(session, run_id) -> dict` and `serialise(catalog) -> bytes` and `content_hash(catalog) -> str` from `app.catalog.build`

- [ ] **Step 1: Write the failing test**

`api/tests/test_catalog_build.py`:

```python
import uuid

import pytest


@pytest.fixture
def catalog(db, tmp_path):
    from app.catalog.build import build_catalog
    from app.seed import seed
    from app.storage import LocalDiskStorage

    seed(db, LocalDiskStorage(tmp_path, "http://t/media"))
    db.flush()
    return build_catalog(db, uuid.uuid4())


def _shows(catalog) -> dict:
    return {s["slug"]: s for section in catalog["sections"] for s in section["shows"]}


def test_sections_follow_reference_order(catalog):
    assert [s["key"] for s in catalog["sections"]] == ["featured", "series", "minisodes", "songs"]


def test_draft_show_is_absent(catalog):
    assert "rhyme-rangers" not in _shows(catalog)


def test_language_variants_collapse_into_one_entry(catalog):
    moti = _shows(catalog)["motis-many-lives"]
    season_one = next(s for s in moti["seasons"] if s["season_number"] == 1)
    entry = next(e for e in season_one["episodes"] if e["episode_number"] == 2)
    assert entry["languages"] == ["en", "hi"]
    assert entry["title"] == "Rain on the Roof"
    assert entry["duration_seconds"] == 540, "canonical language is en, which runs 540s"


def test_each_content_group_appears_once(catalog):
    for show in _shows(catalog).values():
        groups = [
            e["content_group"] for season in show["seasons"] for e in season["episodes"]
        ]
        assert len(groups) == len(set(groups))


def test_lyrical_show_is_not_merged_with_songs(catalog):
    shows = _shows(catalog)
    assert "peblo-songs" in shows
    assert "peblo-songs-lyrical" in shows
    songs_section = next(s for s in catalog["sections"] if s["key"] == "songs")
    assert len(songs_section["shows"]) == 2


def test_season_zero_is_not_a_season(catalog):
    moti = _shows(catalog)["motis-many-lives"]
    assert [s["season_number"] for s in moti["seasons"]] == [1]
    assert len(moti["trailers"]) == 1
    assert moti["trailers"][0]["title"] == "Trailer"


def test_draft_episodes_are_excluded_but_the_show_survives(catalog):
    nest = _shows(catalog)["number-nest"]
    numbers = [e["episode_number"] for s in nest["seasons"] for e in s["episodes"]]
    assert numbers == [1, 2, 3, 4, 5, 6]


def test_downgraded_episode_is_absent(catalog):
    """ep_0036 was downgraded at import, so it must not reach viewers."""
    india = _shows(catalog)["discover-india-with-moti"]
    numbers = [e["episode_number"] for s in india["seasons"] for e in s["episodes"]]
    assert 4 not in numbers


def test_hero_is_the_first_featured_show(catalog):
    assert catalog["hero"]["slug"] == "motis-many-lives"


def test_show_languages_are_the_union_of_its_episodes(catalog):
    assert _shows(catalog)["motis-many-lives"]["languages"] == ["en", "hi"]
    assert _shows(catalog)["curious-cubs"]["languages"] == ["en"]


def test_artwork_urls_are_present_per_surface(catalog):
    moti = _shows(catalog)["motis-many-lives"]
    assert moti["artwork"]["poster"].startswith("http")
    assert moti["artwork"]["banner"].startswith("http")
    episode = moti["seasons"][0]["episodes"][0]
    assert episode["artwork"]["thumbnail"].startswith("http")


def test_build_is_deterministic(db, tmp_path):
    from app.catalog.build import build_catalog, content_hash
    from app.seed import seed
    from app.storage import LocalDiskStorage

    seed(db, LocalDiskStorage(tmp_path, "http://t/media"))
    db.flush()
    first = build_catalog(db, uuid.uuid4())
    second = build_catalog(db, uuid.uuid4())
    assert content_hash(first) == content_hash(second), "run_id must not affect the hash"


def test_serialisation_is_stable_bytes(catalog):
    from app.catalog.build import serialise

    assert serialise(catalog) == serialise(catalog)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_catalog_build.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.catalog'`.

- [ ] **Step 3: Write `api/app/catalog/build.py`**

```python
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
    return {
        (a.kind.value if hasattr(a.kind, "value") else a.kind): storage.url(a.storage_key)
        for a in records
    }


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
                seasons_out.append(
                    {"season_number": season.season_number, "episodes": entries}
                )

        if not seasons_out:
            # Defence in depth. The validation report blocks this case already.
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
    fallback = next((s["shows"] for s in ordered_sections if s["shows"]), [])
    hero_source = featured or fallback

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_catalog_build.py -v && ruff check .`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add api/app/catalog api/tests/test_catalog_build.py
git commit -m "feat(api): deterministic catalogue build with content_group collapsing"
```

---

### Task 11: Publish

**Files:**
- Create: `api/app/catalog/publish.py`
- Modify: `api/app/routers/admin_catalog.py`
- Test: `api/tests/test_publish.py`

**Interfaces:**
- Consumes: `build_catalog`, `serialise`, `content_hash` from Task 10; `build_validation_report` from Task 8; `require_admin` from Task 3
- Produces: `publish(session, storage, user_id) -> PublishRun` and `PublishBlocked` exception from `app.catalog.publish`; routes `POST /admin/catalog/publish`, `GET /admin/catalog/runs`

- [ ] **Step 1: Write the failing test**

`api/tests/test_publish.py`:

```python
import pytest


@pytest.fixture
def storage(tmp_path):
    from app.storage import LocalDiskStorage

    return LocalDiskStorage(tmp_path, "http://t/media")


@pytest.fixture
def seeded(db, storage):
    from app.seed import seed

    seed(db, storage)
    db.flush()


def test_publish_writes_a_run_scoped_file_and_flips_the_pointer(db, storage, seeded, users):
    from app.catalog.publish import publish
    from app.models import CatalogPointer, RunStatus

    run = publish(db, storage, users["admin"].id)
    assert run.status == RunStatus.success
    assert run.catalog_key == f"catalog/runs/{run.run_id}.json"
    assert storage.exists(run.catalog_key)
    assert db.get(CatalogPointer, 1).current_run_id == run.id


def test_publish_never_overwrites_an_existing_file(db, storage, seeded, users):
    """Two publishes over changed data must produce two files, not one."""
    from app.catalog.publish import publish
    from app.models import Show

    first = publish(db, storage, users["admin"].id)
    db.query(Show).filter_by(slug="curious-cubs").one().title = "Curious Cubs Returns"
    db.flush()
    second = publish(db, storage, users["admin"].id)

    assert first.catalog_key != second.catalog_key
    assert storage.exists(first.catalog_key), "the previous catalogue must survive"
    assert storage.exists(second.catalog_key)


def test_publishing_twice_with_no_edits_records_no_change(db, storage, seeded, users):
    from app.catalog.publish import publish
    from app.models import RunStatus

    first = publish(db, storage, users["admin"].id)
    second = publish(db, storage, users["admin"].id)
    assert second.status == RunStatus.no_change
    assert second.catalog_key is None
    assert second.content_hash == first.content_hash


def test_the_pointer_does_not_move_on_a_no_change_run(db, storage, seeded, users):
    from app.catalog.publish import publish
    from app.models import CatalogPointer

    first = publish(db, storage, users["admin"].id)
    publish(db, storage, users["admin"].id)
    assert db.get(CatalogPointer, 1).current_run_id == first.id


def test_publish_records_counts_and_author(db, storage, seeded, users):
    from app.catalog.publish import publish

    run = publish(db, storage, users["admin"].id)
    assert run.started_by == users["admin"].id
    assert run.counts["shows"] == 7
    assert run.counts["episodes"] > 0
    assert run.finished_at is not None


def test_blocking_validation_prevents_any_write(db, storage, seeded, users):
    from app.catalog.publish import PublishBlocked, publish
    from app.models import Episode, RunStatus

    episode = db.query(Episode).filter_by(content_group="motis-many-lives-s01e01").first()
    episode.duration_seconds = None
    db.flush()

    with pytest.raises(PublishBlocked) as exc:
        publish(db, storage, users["admin"].id)

    assert exc.value.run.status == RunStatus.failed
    assert list(tmp_files(storage)) == []
    assert any(
        i["code"] == "episode_missing_duration"
        for g in exc.value.report["groups"]
        for i in g["blocking"]
    )


def tmp_files(storage):
    return storage.root.rglob("catalog/runs/*.json")


def test_a_crash_before_the_pointer_flip_leaves_readers_untouched(
    db, storage, seeded, users, monkeypatch
):
    """The file may land, but until the pointer moves nothing can reach it."""
    from app.catalog import publish as publish_module
    from app.models import CatalogPointer

    first = publish_module.publish(db, storage, users["admin"].id)
    pointer_before = db.get(CatalogPointer, 1).current_run_id
    assert pointer_before == first.id

    from app.models import Show

    db.query(Show).filter_by(slug="curious-cubs").one().title = "Changed"
    db.flush()

    def explode(*args, **kwargs):
        raise RuntimeError("process died after the write")

    monkeypatch.setattr(publish_module, "_flip_pointer", explode)
    with pytest.raises(RuntimeError):
        publish_module.publish(db, storage, users["admin"].id)

    assert db.get(CatalogPointer, 1).current_run_id == pointer_before


def test_publish_route_rejects_an_editor(api, storage, seeded, editor_headers, monkeypatch):
    from app.routers import admin_catalog

    monkeypatch.setattr(admin_catalog, "get_storage", lambda: storage)
    response = api.post("/admin/catalog/publish", headers=editor_headers)
    assert response.status_code == 403
    assert response.json()["errors"][0]["code"] == "forbidden"


def test_publish_route_allows_an_admin(api, storage, seeded, admin_headers, monkeypatch):
    from app.routers import admin_catalog

    monkeypatch.setattr(admin_catalog, "get_storage", lambda: storage)
    response = api.post("/admin/catalog/publish", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_blocked_publish_returns_409_with_the_reasons(
    api, db, storage, seeded, admin_headers, monkeypatch
):
    from app.models import Episode
    from app.routers import admin_catalog

    monkeypatch.setattr(admin_catalog, "get_storage", lambda: storage)
    db.query(Episode).filter_by(content_group="motis-many-lives-s01e01").first().duration_seconds = (
        None
    )
    db.flush()
    response = api.post("/admin/catalog/publish", headers=admin_headers)
    assert response.status_code == 409
    assert response.json()["report"]["can_publish"] is False


def test_run_history_is_newest_first(api, db, storage, seeded, admin_headers, monkeypatch):
    from app.catalog.publish import publish
    from app.models import Show
    from app.routers import admin_catalog

    monkeypatch.setattr(admin_catalog, "get_storage", lambda: storage)
    publish(db, storage, 1)
    db.query(Show).filter_by(slug="curious-cubs").one().title = "Second"
    db.flush()
    publish(db, storage, 1)

    body = api.get("/admin/catalog/runs", headers=admin_headers).json()
    assert len(body["items"]) == 2
    assert body["items"][0]["started_at"] >= body["items"][1]["started_at"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_publish.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.catalog.publish'`.

- [ ] **Step 3: Write `api/app/catalog/publish.py`**

```python
"""Publishing.

Every run writes a file at a key nothing has ever used, then flips a single
row to point at it. That pointer update is the atomic commit point: before it
the new file is unreachable, after it every reader sees the complete file.
Nothing ever overwrites the live catalogue.
"""

import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.build import build_catalog, content_hash, serialise
from app.models import CatalogPointer, PublishRun, RunStatus
from app.storage.base import Storage
from app.validation import build_validation_report

STALE_RUN_MINUTES = 5


class PublishBlocked(Exception):
    def __init__(self, run: PublishRun, report: dict):
        self.run = run
        self.report = report


def _counts(catalog: dict) -> dict:
    shows = [s for section in catalog["sections"] for s in section["shows"]]
    episodes = [e for s in shows for season in s["seasons"] for e in season["episodes"]]
    trailers = [t for s in shows for t in s["trailers"]]
    return {
        "shows": len(shows),
        "episodes": len(episodes),
        "trailers": len(trailers),
        "sections": len([s for s in catalog["sections"] if s["shows"]]),
    }


def _flip_pointer(session: Session, run: PublishRun) -> None:
    """The atomic commit point. Extracted so a test can make it fail."""
    pointer = session.get(CatalogPointer, 1)
    if pointer is None:
        pointer = CatalogPointer(id=1)
        session.add(pointer)
    pointer.current_run_id = run.id
    session.flush()


def publish(session: Session, storage: Storage, user_id: int | None) -> PublishRun:
    run_id = uuid.uuid4()
    run = PublishRun(run_id=run_id, started_by=user_id, status=RunStatus.running)
    session.add(run)
    session.flush()

    report = build_validation_report(session)
    if not report.can_publish:
        run.status = RunStatus.failed
        run.finished_at = datetime.now(UTC)
        run.error = {"blocking_count": report.blocking_count}
        session.flush()
        raise PublishBlocked(run, asdict(report))

    catalog = build_catalog(session, run_id)
    digest = content_hash(catalog)
    run.content_hash = digest

    pointer = session.get(CatalogPointer, 1)
    current = session.get(PublishRun, pointer.current_run_id) if pointer else None
    if current is not None and current.content_hash == digest:
        run.status = RunStatus.no_change
        run.finished_at = datetime.now(UTC)
        run.counts = _counts(catalog)
        session.flush()
        return run

    key = f"catalog/runs/{run_id}.json"
    storage.put(key, serialise(catalog), "application/json")

    # A write that reported success but landed corrupt must not become live.
    written = storage.get(key)
    if content_hash(_loads(written)) != digest:
        run.status = RunStatus.failed
        run.finished_at = datetime.now(UTC)
        run.error = {"message": "The catalogue file did not read back correctly."}
        session.flush()
        raise RuntimeError("catalogue verification failed after write")

    run.catalog_key = key
    _flip_pointer(session, run)
    run.status = RunStatus.success
    run.counts = _counts(catalog)
    run.finished_at = datetime.now(UTC)
    session.flush()
    return run


def _loads(data: bytes) -> dict:
    import json

    return json.loads(data)


def sweep_stale_runs(session: Session) -> int:
    """Marks runs abandoned by a dead process, so run history never shows a
    permanently spinning run. Called on API startup."""
    cutoff = datetime.now(UTC) - timedelta(minutes=STALE_RUN_MINUTES)
    stale = session.scalars(
        select(PublishRun).where(
            PublishRun.status == RunStatus.running, PublishRun.started_at < cutoff
        )
    ).all()
    for run in stale:
        run.status = RunStatus.failed
        run.finished_at = datetime.now(UTC)
        run.error = {"message": "This publish did not finish. It was probably interrupted."}
    session.flush()
    return len(stale)
```

- [ ] **Step 4: Add the publish and runs routes to `api/app/routers/admin_catalog.py`**

```python
from fastapi import Query
from sqlalchemy import select

from app.auth import require_admin
from app.catalog.publish import PublishBlocked, publish
from app.models import PublishRun
from app.storage import get_storage


def _run_out(run: PublishRun) -> dict:
    return {
        "id": run.id,
        "run_id": str(run.run_id),
        "status": run.status.value if hasattr(run.status, "value") else run.status,
        "started_by": run.started_by,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "counts": run.counts,
        "catalog_key": run.catalog_key,
        "content_hash": run.content_hash,
        "error": run.error,
    }


@router.post("/catalog/publish")
def publish_catalog(
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
) -> dict:
    try:
        run = publish(session, get_storage(), user.id)
    except PublishBlocked as blocked:
        return JSONResponse(
            status_code=409,
            content={
                "errors": [
                    {
                        "code": "publish_blocked",
                        "message": (
                            f"{blocked.report['blocking_count']} problems need fixing "
                            "before this catalogue can go live."
                        ),
                        "field": None,
                    }
                ],
                "report": blocked.report,
            },
        )
    return _run_out(run)


@router.get("/catalog/runs")
def list_runs(
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> dict:
    runs = session.scalars(
        select(PublishRun).order_by(PublishRun.started_at.desc()).limit(limit)
    ).all()
    return {"items": [_run_out(r) for r in runs]}
```

Add `from fastapi.responses import JSONResponse` to the imports at the top of the file.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_publish.py -v && ruff check .`
Expected: 11 passed. If `test_publish_records_counts_and_author` reports a different show count, verify against the seed: 8 shows minus `rhyme-rangers`, which is draft, leaves 7.

- [ ] **Step 6: Commit**

```bash
git add api/app/catalog/publish.py api/app/routers/admin_catalog.py api/tests/test_publish.py
git commit -m "feat(api): atomic idempotent publish with recorded runs"
```

---

### Task 12: Read path and search

**Files:**
- Create: `api/app/catalog/serve.py`, `api/app/catalog/search.py`, `api/app/routers/catalog.py`
- Modify: `api/app/main.py`
- Test: `api/tests/test_catalog_read.py`

**Interfaces:**
- Consumes: `CatalogPointer`, `PublishRun` from Task 2; storage from Task 4
- Produces: `current_catalog(session, storage) -> dict | None` and `invalidate_cache()` from `app.catalog.serve`; `search_catalog(catalog, q, category, language, section) -> dict` from `app.catalog.search`; routes `GET /catalog`, `GET /catalog/search`

- [ ] **Step 1: Write the failing test**

`api/tests/test_catalog_read.py`:

```python
import pytest


@pytest.fixture
def storage(tmp_path):
    from app.storage import LocalDiskStorage

    return LocalDiskStorage(tmp_path, "http://t/media")


@pytest.fixture
def published(db, storage, users):
    from app.catalog.publish import publish
    from app.catalog.serve import invalidate_cache
    from app.seed import seed

    seed(db, storage)
    db.flush()
    run = publish(db, storage, users["admin"].id)
    invalidate_cache()
    return run


@pytest.fixture
def viewer(api, storage, monkeypatch):
    from app.routers import catalog as catalog_router

    monkeypatch.setattr(catalog_router, "get_storage", lambda: storage)
    return api


def test_catalog_serves_the_published_file(viewer, published):
    response = viewer.get("/catalog")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == str(published.run_id)
    assert len(body["sections"]) == 4


def test_catalog_needs_no_token(viewer, published):
    assert "authorization" not in {k.lower() for k in viewer.headers}
    assert viewer.get("/catalog").status_code == 200


def test_catalog_before_any_publish_is_a_clear_empty(api, db, monkeypatch, storage):
    from app.routers import catalog as catalog_router

    monkeypatch.setattr(catalog_router, "get_storage", lambda: storage)
    response = api.get("/catalog")
    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "catalog_not_published"


def test_search_matches_show_title(viewer, published):
    body = viewer.get("/catalog/search?q=Moti").json()
    slugs = {r["show"]["slug"] for r in body["results"]}
    assert "motis-many-lives" in slugs


def test_search_matches_episode_title_and_names_its_show(viewer, published):
    """Episode titles repeat across all eight shows, so a result is useless
    unless it says which show it belongs to."""
    body = viewer.get("/catalog/search?q=The Lost Kite").json()
    assert len(body["results"]) > 1
    for result in body["results"]:
        assert result["show"]["title"]
        assert result["match"] in {"show", "episode", "category"}


def test_search_matches_category(viewer, published):
    body = viewer.get("/catalog/search?q=folk").json()
    assert body["total"] > 0


def test_filters_compose(viewer, published):
    both = viewer.get("/catalog/search?section=songs&language=hi").json()
    for result in both["results"]:
        assert result["show"]["slug"] in {"peblo-songs", "peblo-songs-lyrical"}
        assert "hi" in result["show"]["languages"]
    assert all(r["show"]["slug"] != "peblo-songs-lyrical" for r in both["results"]), (
        "the lyrical show is English only, so a hi filter must exclude it"
    )


def test_unknown_filter_value_returns_an_empty_result_not_an_error(viewer, published):
    body = viewer.get("/catalog/search?category=dinosaurs").json()
    assert body["total"] == 0
    assert body["results"] == []


def test_search_is_case_insensitive(viewer, published):
    lower = viewer.get("/catalog/search?q=moti").json()["total"]
    upper = viewer.get("/catalog/search?q=MOTI").json()["total"]
    assert lower == upper > 0


def test_a_new_publish_becomes_visible(viewer, db, storage, published, users):
    from app.catalog.publish import publish
    from app.catalog.serve import invalidate_cache
    from app.models import Show

    db.query(Show).filter_by(slug="curious-cubs").one().title = "Curious Cubs Returns"
    db.flush()
    publish(db, storage, users["admin"].id)
    invalidate_cache()

    titles = {
        s["title"] for section in viewer.get("/catalog").json()["sections"] for s in section["shows"]
    }
    assert "Curious Cubs Returns" in titles
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_catalog_read.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.catalog.serve'`.

- [ ] **Step 3: Write `api/app/catalog/serve.py`**

```python
"""Read path.

The catalogue a run produced never changes, so caching it by run id is safe
forever. Only the pointer moves, and it is cheap to re-read on a short TTL.
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
    global _pointer_cache
    _pointer_cache = (0.0, None)
    _catalog_cache.clear()


def _current_key(session: Session) -> str | None:
    global _pointer_cache
    cached_at, key = _pointer_cache
    if time.monotonic() - cached_at < POINTER_TTL_SECONDS:
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
```

- [ ] **Step 4: Write `api/app/catalog/search.py`**

```python
"""Search over the published catalogue.

Deliberately a linear scan over the same artifact the viewer renders. That
makes it impossible for search to return something the browse pages cannot
show, and impossible for it to leak an unpublished row.

Scale ceiling: fine to roughly 10k entries and a few MB. Past that, build a
catalog_entries projection table at publish time and query it with a Postgres
tsvector index, which also buys stemming and ranking. Past roughly a million
entries, or as soon as typo tolerance matters, move to a dedicated engine fed
by the same publish job.
"""


def _show_summary(show: dict, section: str) -> dict:
    return {
        "slug": show["slug"],
        "title": show["title"],
        "synopsis": show["synopsis"],
        "section": section,
        "categories": show["categories"],
        "languages": show["languages"],
        "artwork": show["artwork"],
    }


def search_catalog(
    catalog: dict,
    q: str | None = None,
    category: str | None = None,
    language: str | None = None,
    section: str | None = None,
) -> dict:
    needle = (q or "").strip().lower()
    results: list[dict] = []

    for section_block in catalog["sections"]:
        if section and section_block["key"] != section:
            continue
        for show in section_block["shows"]:
            if category and category not in show["categories"]:
                continue
            if language and language not in show["languages"]:
                continue

            if not needle:
                results.append(
                    {
                        "match": "show",
                        "show": _show_summary(show, section_block["key"]),
                        "episode": None,
                    }
                )
                continue

            if needle in show["title"].lower():
                results.append(
                    {
                        "match": "show",
                        "show": _show_summary(show, section_block["key"]),
                        "episode": None,
                    }
                )
                continue

            if any(needle in c.lower() for c in show["categories"]):
                results.append(
                    {
                        "match": "category",
                        "show": _show_summary(show, section_block["key"]),
                        "episode": None,
                    }
                )
                continue

            for season in show["seasons"]:
                for episode in season["episodes"]:
                    if needle not in episode["title"].lower():
                        continue
                    if language and language not in episode["languages"]:
                        continue
                    results.append(
                        {
                            "match": "episode",
                            "show": _show_summary(show, section_block["key"]),
                            "episode": {
                                "content_group": episode["content_group"],
                                "season_number": season["season_number"],
                                "episode_number": episode["episode_number"],
                                "title": episode["title"],
                                "duration_seconds": episode["duration_seconds"],
                                "languages": episode["languages"],
                                "artwork": episode["artwork"],
                            },
                        }
                    )

    return {"total": len(results), "results": results}
```

- [ ] **Step 5: Write `api/app/routers/catalog.py`**

```python
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
```

- [ ] **Step 6: Register the router in `api/app/main.py`**

```python
from app.routers import admin_catalog, artwork, auth, catalog, episodes, health, shows

app.include_router(catalog.router)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_catalog_read.py -v && ruff check .`
Expected: 10 passed.

- [ ] **Step 8: Commit**

```bash
git add api/app/catalog/serve.py api/app/catalog/search.py api/app/routers/catalog.py api/app/main.py api/tests/test_catalog_read.py
git commit -m "feat(api): public catalogue read path with composing server-side search"
```

---

### Task 13: Rollback (stretch goal)

**Files:**
- Modify: `api/app/catalog/publish.py`, `api/app/routers/admin_catalog.py`
- Test: `api/tests/test_rollback.py`

**Interfaces:**
- Consumes: `publish`, `_flip_pointer` from Task 11
- Produces: `rollback(session, storage, run_db_id) -> PublishRun` from `app.catalog.publish`; route `POST /admin/catalog/rollback`

- [ ] **Step 1: Write the failing test**

`api/tests/test_rollback.py`:

```python
import pytest


@pytest.fixture
def storage(tmp_path):
    from app.storage import LocalDiskStorage

    return LocalDiskStorage(tmp_path, "http://t/media")


@pytest.fixture
def two_runs(db, storage, users):
    from app.catalog.publish import publish
    from app.models import Show
    from app.seed import seed

    seed(db, storage)
    db.flush()
    first = publish(db, storage, users["admin"].id)
    db.query(Show).filter_by(slug="curious-cubs").one().title = "Curious Cubs Returns"
    db.flush()
    second = publish(db, storage, users["admin"].id)
    return first, second


def test_rollback_moves_the_pointer_back(db, storage, two_runs):
    from app.catalog.publish import rollback
    from app.models import CatalogPointer

    first, second = two_runs
    assert db.get(CatalogPointer, 1).current_run_id == second.id
    rollback(db, storage, first.id)
    assert db.get(CatalogPointer, 1).current_run_id == first.id


def test_rollback_serves_the_older_catalogue(db, storage, two_runs, api, monkeypatch):
    from app.catalog.publish import rollback
    from app.catalog.serve import invalidate_cache
    from app.routers import catalog as catalog_router

    monkeypatch.setattr(catalog_router, "get_storage", lambda: storage)
    first, _ = two_runs
    rollback(db, storage, first.id)
    invalidate_cache()

    titles = {
        s["title"] for section in api.get("/catalog").json()["sections"] for s in section["shows"]
    }
    assert "Curious Cubs" in titles
    assert "Curious Cubs Returns" not in titles


def test_rollback_to_a_failed_run_is_refused(db, storage, two_runs, users):
    from app.catalog.publish import rollback
    from app.errors import ApiException
    from app.models import PublishRun, RunStatus

    bad = PublishRun(run_id=__import__("uuid").uuid4(), status=RunStatus.failed)
    db.add(bad)
    db.flush()
    with pytest.raises(ApiException) as exc:
        rollback(db, storage, bad.id)
    assert exc.value.errors[0].code == "rollback_invalid_target"


def test_rollback_route_rejects_an_editor(api, storage, two_runs, editor_headers, monkeypatch):
    from app.routers import admin_catalog

    monkeypatch.setattr(admin_catalog, "get_storage", lambda: storage)
    first, _ = two_runs
    response = api.post(
        "/admin/catalog/rollback", headers=editor_headers, json={"run_db_id": first.id}
    )
    assert response.status_code == 403


def test_rollback_route_allows_an_admin(api, storage, two_runs, admin_headers, monkeypatch):
    from app.routers import admin_catalog

    monkeypatch.setattr(admin_catalog, "get_storage", lambda: storage)
    first, _ = two_runs
    response = api.post(
        "/admin/catalog/rollback", headers=admin_headers, json={"run_db_id": first.id}
    )
    assert response.status_code == 200
    assert response.json()["id"] == first.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_rollback.py -v`
Expected: FAIL with `ImportError: cannot import name 'rollback'`.

- [ ] **Step 3: Append `rollback` to `api/app/catalog/publish.py`**

```python
def rollback(session: Session, storage: Storage, run_db_id: int) -> PublishRun:
    """Point the catalogue at an earlier successful run.

    This is roughly ten lines rather than a project because publishing never
    overwrites, so every previous catalogue file is still exactly where it was.
    """
    from app.errors import ApiError, ApiException

    target = session.get(PublishRun, run_db_id)
    if target is None or target.status != RunStatus.success or not target.catalog_key:
        raise ApiException(
            422,
            [
                ApiError(
                    "rollback_invalid_target",
                    "You can only roll back to a publish that finished successfully.",
                    "run_db_id",
                )
            ],
        )
    if not storage.exists(target.catalog_key):
        raise ApiException(
            422,
            [
                ApiError(
                    "rollback_file_missing",
                    "That catalogue file is no longer in storage, so we cannot roll back to it.",
                    "run_db_id",
                )
            ],
        )
    _flip_pointer(session, target)
    return target
```

- [ ] **Step 4: Add the route to `api/app/routers/admin_catalog.py`**

```python
from pydantic import BaseModel

from app.catalog.publish import rollback


class RollbackRequest(BaseModel):
    run_db_id: int


@router.post("/catalog/rollback")
def rollback_catalog(
    body: RollbackRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> dict:
    return _run_out(rollback(session, get_storage(), body.run_db_id))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_rollback.py -v && ruff check .`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add api/app/catalog/publish.py api/app/routers/admin_catalog.py api/tests/test_rollback.py
git commit -m "feat(api): rollback to a previous successful publish run"
```

---

### Task 14: Readiness, startup sweep, full suite green

**Files:**
- Modify: `api/app/routers/health.py`, `api/app/main.py`
- Test: `api/tests/test_readiness.py`

**Interfaces:**
- Consumes: `sweep_stale_runs` from Task 11; `current_catalog` from Task 12
- Produces: route `GET /readyz` returning `{"status": "ready" | "degraded", "checks": {"database": bool, "storage": bool, "catalog": bool}}`

- [ ] **Step 1: Write the failing test**

`api/tests/test_readiness.py`:

```python
import pytest


@pytest.fixture
def storage(tmp_path):
    from app.storage import LocalDiskStorage

    return LocalDiskStorage(tmp_path, "http://t/media")


def test_healthz_touches_no_dependency(client):
    """Liveness must stay green when the database is unreachable, otherwise
    a database blip makes the orchestrator kill healthy containers."""
    assert client.get("/healthz").json() == {"status": "ok"}


def test_readyz_is_degraded_before_a_publish(api, db, storage, monkeypatch):
    from app.routers import health

    monkeypatch.setattr(health, "get_storage", lambda: storage)
    body = api.get("/readyz").json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"] is True
    assert body["checks"]["catalog"] is False


def test_readyz_is_ready_after_a_publish(api, db, storage, users, monkeypatch):
    from app.catalog.publish import publish
    from app.catalog.serve import invalidate_cache
    from app.routers import health
    from app.seed import seed

    monkeypatch.setattr(health, "get_storage", lambda: storage)
    seed(db, storage)
    db.flush()
    publish(db, storage, users["admin"].id)
    invalidate_cache()

    body = api.get("/readyz").json()
    assert body["status"] == "ready"
    assert all(body["checks"].values())


def test_sweep_fails_runs_abandoned_by_a_dead_process(db):
    import uuid
    from datetime import UTC, datetime, timedelta

    from app.catalog.publish import sweep_stale_runs
    from app.models import PublishRun, RunStatus

    stale = PublishRun(
        run_id=uuid.uuid4(),
        status=RunStatus.running,
        started_at=datetime.now(UTC) - timedelta(minutes=30),
    )
    fresh = PublishRun(run_id=uuid.uuid4(), status=RunStatus.running)
    db.add_all([stale, fresh])
    db.flush()

    assert sweep_stale_runs(db) == 1
    assert stale.status == RunStatus.failed
    assert "interrupted" in stale.error["message"]
    assert fresh.status == RunStatus.running
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_readiness.py -v`
Expected: FAIL, 404 on `/readyz`.

- [ ] **Step 3: Add readiness to `api/app/routers/health.py`**

```python
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.catalog.serve import current_catalog
from app.db import get_session
from app.storage import get_storage


@router.get("/readyz")
def readyz(session: Session = Depends(get_session)) -> JSONResponse:
    """Readiness, unlike liveness, is allowed to fail on a dependency.

    The catalog check is the interesting one: it proves the pointer resolves
    to a file that actually reads, which is the state the viewer depends on.
    """
    checks = {"database": False, "storage": False, "catalog": False}
    try:
        session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass

    storage = get_storage()
    try:
        storage.exists("readyz-probe")
        checks["storage"] = True
    except Exception:
        pass

    try:
        checks["catalog"] = current_catalog(session, storage) is not None
    except Exception:
        pass

    ready = all(checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "degraded", "checks": checks},
    )
```

- [ ] **Step 4: Run the sweep on startup in `api/app/main.py`**

```python
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(_: FastAPI):
    from app.catalog.publish import sweep_stale_runs
    from app.db import SessionLocal

    session = SessionLocal()
    try:
        swept = sweep_stale_runs(session)
        session.commit()
        if swept:
            print(f"Marked {swept} interrupted publish run(s) as failed.")
    except Exception as exc:
        print(f"Startup sweep skipped: {exc}")
    finally:
        session.close()
    yield


app = FastAPI(title="Peblo TV Mini API", lifespan=lifespan)
```

- [ ] **Step 5: Run the full suite**

Run: `cd api && python -m pytest tests -v && ruff check .`
Expected: every test passes. Record the count for the README.

- [ ] **Step 6: Verify migrations still match the models**

```bash
cd api && alembic downgrade base && alembic upgrade head && alembic check
```
Expected: no pending changes detected.

- [ ] **Step 7: Commit**

```bash
git add api/app/routers/health.py api/app/main.py api/tests/test_readiness.py
git commit -m "feat(api): readiness probe and startup sweep for interrupted runs"
```

---

## Backend acceptance checklist

Before moving to the frontends plan, confirm each of these by running it:

- [ ] `pytest api/tests` passes with no skips
- [ ] `ruff check api` is clean
- [ ] `alembic upgrade head` from an empty database succeeds, `alembic check` reports no drift
- [ ] `python -m app.seed` prints 8 shows, 94 episodes, 1 rejected, 1 downgraded
- [ ] An editor token receives 403 from `POST /admin/catalog/publish`
- [ ] `GET /catalog` returns 4 sections, hero `motis-many-lives`, and no `rhyme-rangers`
- [ ] Publishing twice in a row records the second run as `no_change`
- [ ] `GET /admin/validation-report` lists exactly two import problems
