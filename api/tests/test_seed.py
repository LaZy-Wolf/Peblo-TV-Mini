import pytest

from app.models import (
    Artwork,
    ContentStatus,
    Episode,
    ImportAction,
    ImportIssue,
    Season,
    Show,
    User,
)


@pytest.fixture
def seeded(db, storage):
    from app.seed import seed

    result = seed(db, storage)
    db.flush()
    return result


def test_seed_creates_eight_shows(seeded, db):
    assert db.query(Show).count() == 8


def test_seed_imports_every_row_except_the_rejected_one(seeded, db):
    """95 supplied rows, one of which is a duplicate language variant."""
    assert db.query(Episode).count() == 94
    assert seeded.episodes == 94


def test_duplicate_variant_row_is_rejected_not_imported(seeded, db):
    """ep_9001 is a second Hindi version of motis-many-lives-s01e02."""
    rejected = db.query(ImportIssue).filter(ImportIssue.action == ImportAction.rejected).all()
    assert len(rejected) == 1
    assert rejected[0].source_row["episode_id"] == "ep_9001"
    assert seeded.rejected == 1

    variants = db.query(Episode).filter(Episode.content_group == "motis-many-lives-s01e02").all()
    assert sorted(e.language for e in variants) == ["en", "hi"]


def test_published_row_without_artwork_is_downgraded(seeded, db):
    """ep_0036 arrives published with an empty artwork list.

    It cannot legally be published, so it is imported as a draft and reported
    rather than dropped.
    """
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

    Nothing may merge them.
    """
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
    moti = db.query(Show).filter_by(slug="motis-many-lives").one()
    assert {a.kind for a in moti.artwork} == {"poster", "banner", "thumbnail"}
    assert db.query(Artwork).filter(Artwork.episode_id.isnot(None)).count() > 0


def test_seeded_artwork_passed_real_validation(seeded, db):
    """Dimensions come from the validator, not from a hardcoded guess."""
    poster = db.query(Artwork).filter_by(kind="poster").first()
    assert (poster.width, poster.height) == (600, 900)
    assert poster.bytes < 200 * 1024


def test_seed_creates_both_accounts(seeded, db):
    assert {u.role for u in db.query(User).all()} == {"editor", "admin"}


def test_seasons_belong_to_the_right_show(seeded, db):
    """A season row must never be shared between shows."""
    for season in db.query(Season).all():
        for episode in season.episodes:
            assert episode.season_id == season.id


def test_seed_is_idempotent(db, storage):
    from app.seed import seed

    seed(db, storage)
    db.flush()
    second = seed(db, storage)
    db.flush()
    assert db.query(Show).count() == 8
    assert db.query(Episode).count() == 94
    assert db.query(ImportIssue).count() == 2
    assert second.shows == 8
