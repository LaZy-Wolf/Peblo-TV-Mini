import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Artwork, ArtworkKind, ContentStatus, Episode, Season, Show


def _show(db, slug="s1"):
    show = Show(slug=slug, title="T", synopsis="", section="series", categories=["music"])
    db.add(show)
    db.flush()
    season = Season(show_id=show.id, season_number=1)
    db.add(season)
    db.flush()
    return show, season


def test_content_group_language_pair_is_unique(db):
    _, season = _show(db)
    db.add(
        Episode(
            season_id=season.id,
            episode_number=1,
            title="A",
            language="hi",
            content_group="g1",
            status=ContentStatus.published,
        )
    )
    db.flush()
    db.add(
        Episode(
            season_id=season.id,
            episode_number=2,
            title="B",
            language="hi",
            content_group="g1",
            status=ContentStatus.published,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_same_content_group_different_language_is_allowed(db):
    _, season = _show(db)
    for i, lang in enumerate(["en", "hi"], start=1):
        db.add(
            Episode(
                season_id=season.id,
                episode_number=i,
                title="A",
                language=lang,
                content_group="g1",
            )
        )
    db.flush()
    assert db.query(Episode).count() == 2


def test_artwork_requires_exactly_one_owner(db):
    db.add(
        Artwork(
            show_id=None,
            episode_id=None,
            kind=ArtworkKind.poster,
            storage_key="k",
            width=600,
            height=900,
            bytes=100,
            checksum="c",
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_a_show_may_hold_only_one_poster(db):
    show, _ = _show(db)
    for _ in range(2):
        db.add(
            Artwork(
                show_id=show.id,
                kind=ArtworkKind.poster,
                storage_key="k",
                width=600,
                height=900,
                bytes=100,
                checksum="c",
            )
        )
    with pytest.raises(IntegrityError):
        db.flush()


def test_show_slug_is_unique(db):
    _show(db, "dup")
    db.add(Show(slug="dup", title="T2", synopsis="", categories=[]))
    with pytest.raises(IntegrityError):
        db.flush()


def test_status_round_trips_as_a_plain_string(db):
    """StrEnum values must land in the database as their value, not as
    'ContentStatus.published', which is what a str-mixin Enum would risk."""
    show, _ = _show(db, "status-check")
    show.status = ContentStatus.published
    db.flush()
    db.expire(show)
    assert show.status == "published"
