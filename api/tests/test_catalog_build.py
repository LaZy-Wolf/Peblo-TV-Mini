import uuid

import pytest

from app.catalog.build import build_catalog, content_hash, serialise
from app.seed import seed


@pytest.fixture
def catalog(db, storage):
    seed(db, storage)
    db.flush()
    return build_catalog(db, uuid.uuid4())


def _shows(catalog) -> dict:
    return {s["slug"]: s for section in catalog["sections"] for s in section["shows"]}


def test_sections_follow_reference_order(catalog):
    assert [s["key"] for s in catalog["sections"]] == [
        "featured",
        "series",
        "minisodes",
        "songs",
    ]


def test_draft_show_is_absent(catalog):
    assert "rhyme-rangers" not in _shows(catalog)


def test_seven_shows_reach_the_catalogue(catalog):
    """Eight seeded shows, minus rhyme-rangers, which is entirely draft."""
    assert len(_shows(catalog)) == 7


def test_language_variants_collapse_into_one_entry(catalog):
    moti = _shows(catalog)["motis-many-lives"]
    season_one = next(s for s in moti["seasons"] if s["season_number"] == 1)
    entry = next(e for e in season_one["episodes"] if e["episode_number"] == 2)
    assert entry["languages"] == ["en", "hi"]
    assert entry["title"] == "Rain on the Roof"
    assert entry["duration_seconds"] == 540, "canonical language is en, which runs 540s"


def test_each_content_group_appears_once(catalog):
    for show in _shows(catalog).values():
        groups = [e["content_group"] for season in show["seasons"] for e in season["episodes"]]
        assert len(groups) == len(set(groups))


def test_lyrical_show_is_not_merged_with_songs(catalog):
    """Identical episode titles, distinct content groups. Nothing may merge them."""
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


def test_shows_without_a_trailer_have_an_empty_trailer_list(catalog):
    assert _shows(catalog)["curious-cubs"]["trailers"] == []


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


def test_episodes_are_ordered_by_number(catalog):
    for show in _shows(catalog).values():
        for season in show["seasons"]:
            numbers = [e["episode_number"] for e in season["episodes"]]
            assert numbers == sorted(numbers)


def test_shows_within_a_section_are_ordered_by_title(catalog):
    for section in catalog["sections"]:
        titles = [s["title"] for s in section["shows"]]
        assert titles == sorted(titles)


def test_build_is_deterministic(db, storage):
    """run_id and generated_at must not affect the content hash."""
    seed(db, storage)
    db.flush()
    first = build_catalog(db, uuid.uuid4())
    second = build_catalog(db, uuid.uuid4())
    assert first["run_id"] != second["run_id"]
    assert content_hash(first) == content_hash(second)


def test_serialisation_is_stable_bytes(catalog):
    assert serialise(catalog) == serialise(catalog)


def test_a_real_edit_changes_the_hash(db, storage):
    from app.models import Show

    seed(db, storage)
    db.flush()
    before = content_hash(build_catalog(db, uuid.uuid4()))
    db.query(Show).filter_by(slug="curious-cubs").one().title = "Curious Cubs Returns"
    db.flush()
    assert content_hash(build_catalog(db, uuid.uuid4())) != before
