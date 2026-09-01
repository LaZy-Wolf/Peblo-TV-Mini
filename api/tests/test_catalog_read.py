import pytest

from app.catalog.publish import publish
from app.catalog.serve import invalidate_cache
from app.models import Show
from app.seed import seed


@pytest.fixture(autouse=True)
def clean_cache():
    """The read path caches by run id, and tests share a process."""
    invalidate_cache()
    yield
    invalidate_cache()


@pytest.fixture
def viewer(api, storage, monkeypatch):
    from app.routers import catalog as catalog_router

    monkeypatch.setattr(catalog_router, "get_storage", lambda: storage)
    return api


@pytest.fixture
def published(db, storage, users):
    seed(db, storage)
    db.flush()
    run = publish(db, storage, users["admin"].id)
    invalidate_cache()
    return run


def test_catalog_serves_the_published_file(viewer, published):
    response = viewer.get("/catalog")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == str(published.run_id)
    assert len(body["sections"]) == 4


def test_catalog_needs_no_token(viewer, published):
    """The viewer holds no credentials at all."""
    assert "authorization" not in {k.lower() for k in viewer.headers}
    assert viewer.get("/catalog").status_code == 200


def test_catalog_before_any_publish_is_a_clear_error(viewer, db):
    response = viewer.get("/catalog")
    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "catalog_not_published"


def test_search_matches_show_title(viewer, published):
    body = viewer.get("/catalog/search?q=Moti").json()
    slugs = {r["show"]["slug"] for r in body["results"]}
    assert "motis-many-lives" in slugs


def test_search_matches_episode_title_and_names_its_show(viewer, published):
    """Episode titles repeat across all eight shows, so a result is useless
    unless it says which show and position it belongs to."""
    body = viewer.get("/catalog/search?q=The Lost Kite").json()
    assert body["total"] > 1
    for result in body["results"]:
        assert result["show"]["title"]
        assert result["match"] in {"show", "episode", "category"}
        if result["match"] == "episode":
            assert result["episode"]["season_number"] is not None
            assert result["episode"]["episode_number"] is not None


def test_search_matches_category(viewer, published):
    body = viewer.get("/catalog/search?q=folk").json()
    assert body["total"] > 0
    assert all(r["match"] == "category" for r in body["results"])


def test_search_with_no_query_returns_every_show(viewer, published):
    body = viewer.get("/catalog/search").json()
    assert body["total"] == 7


def test_section_filter_narrows(viewer, published):
    body = viewer.get("/catalog/search?section=songs").json()
    assert {r["show"]["slug"] for r in body["results"]} == {
        "peblo-songs",
        "peblo-songs-lyrical",
    }


def test_filters_compose(viewer, published):
    """section AND language together, not one silently winning."""
    body = viewer.get("/catalog/search?section=songs&language=hi").json()
    slugs = {r["show"]["slug"] for r in body["results"]}
    assert slugs == {"peblo-songs"}, "the lyrical show is English only"


def test_category_and_language_compose(viewer, published):
    both = viewer.get("/catalog/search?category=india&language=hi").json()
    for result in both["results"]:
        assert "india" in result["show"]["categories"]
        assert "hi" in result["show"]["languages"]


def test_unknown_filter_value_returns_an_empty_result_not_an_error(viewer, published):
    body = viewer.get("/catalog/search?category=dinosaurs").json()
    assert body["total"] == 0
    assert body["results"] == []


def test_search_is_case_insensitive(viewer, published):
    lower = viewer.get("/catalog/search?q=moti").json()["total"]
    upper = viewer.get("/catalog/search?q=MOTI").json()["total"]
    assert lower == upper > 0


def test_search_never_returns_unpublished_content(viewer, published):
    """rhyme-rangers is draft, so no query may surface it."""
    for query in ("rhyme", "Rhyme Rangers", "The Lost Kite"):
        body = viewer.get(f"/catalog/search?q={query}").json()
        assert all(r["show"]["slug"] != "rhyme-rangers" for r in body["results"])


def test_a_new_publish_becomes_visible(viewer, db, storage, published, users):
    db.query(Show).filter_by(slug="curious-cubs").one().title = "Curious Cubs Returns"
    db.flush()
    publish(db, storage, users["admin"].id)
    invalidate_cache()

    titles = {
        s["title"]
        for section in viewer.get("/catalog").json()["sections"]
        for s in section["shows"]
    }
    assert "Curious Cubs Returns" in titles
