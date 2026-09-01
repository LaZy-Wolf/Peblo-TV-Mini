import pytest

from app.models import Artwork, ArtworkKind, ContentStatus, Episode, Season, Show


@pytest.fixture
def show(db):
    record = Show(slug="alpha", title="Alpha", synopsis="", section="series", categories=["music"])
    db.add(record)
    db.flush()
    db.add(Season(show_id=record.id, season_number=1))
    db.flush()
    return record


def _add_thumbnail(db, episode_id):
    db.add(
        Artwork(
            episode_id=episode_id,
            kind=ArtworkKind.thumbnail,
            storage_key=f"k{episode_id}",
            width=640,
            height=360,
            bytes=1000,
            checksum="c",
        )
    )
    db.flush()


def _episode(db, show, number, **overrides):
    fields = {
        "season_id": show.seasons[0].id,
        "episode_number": number,
        "title": f"E{number}",
        "duration_seconds": 300,
        "language": "en",
        "content_group": f"alpha-s01e{number:02d}",
    }
    fields.update(overrides)
    episode = Episode(**fields)
    db.add(episode)
    db.flush()
    return episode


def test_create_show_requires_auth(api):
    assert api.post("/admin/shows", json={"slug": "x", "title": "X"}).status_code == 401


def test_create_and_list_shows(api, editor_headers):
    created = api.post(
        "/admin/shows",
        headers=editor_headers,
        json={"slug": "beta", "title": "Beta", "section": "songs", "categories": ["music"]},
    )
    assert created.status_code == 201
    listed = api.get("/admin/shows", headers=editor_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_duplicate_slug_is_a_readable_conflict(api, editor_headers, show):
    response = api.post(
        "/admin/shows", headers=editor_headers, json={"slug": "alpha", "title": "Other"}
    )
    assert response.status_code == 409
    assert response.json()["errors"][0]["code"] == "duplicate_slug"


def test_unknown_section_is_rejected_with_the_allowed_list(api, editor_headers):
    response = api.post(
        "/admin/shows",
        headers=editor_headers,
        json={"slug": "g", "title": "G", "section": "cartoons"},
    )
    assert response.status_code == 422
    error = response.json()["errors"][0]
    assert error["code"] == "unknown_section"
    assert "featured" in error["message"]


def test_unknown_category_is_rejected(api, editor_headers):
    response = api.post(
        "/admin/shows",
        headers=editor_headers,
        json={"slug": "g", "title": "G", "categories": ["dinosaurs"]},
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "unknown_category"


def test_show_detail_includes_artwork_urls(api, editor_headers, db, show):
    db.add(
        Artwork(
            show_id=show.id,
            kind=ArtworkKind.poster,
            storage_key="p",
            width=600,
            height=900,
            bytes=10,
            checksum="c",
        )
    )
    db.flush()
    body = api.get(f"/admin/shows/{show.id}", headers=editor_headers).json()
    assert body["artwork"]["poster"].endswith("/p")


def test_publishing_a_show_without_a_section_is_refused(api, editor_headers, db, show):
    show.section = None
    db.flush()
    response = api.patch(
        f"/admin/shows/{show.id}", headers=editor_headers, json={"status": "published"}
    )
    assert response.status_code == 422
    codes = {e["code"] for e in response.json()["errors"]}
    assert "show_missing_section" in codes


def test_publishing_a_show_with_no_published_episodes_is_refused(api, editor_headers, db, show):
    _episode(db, show, 1)
    response = api.patch(
        f"/admin/shows/{show.id}", headers=editor_headers, json={"status": "published"}
    )
    assert response.status_code == 422
    assert "show_no_published_episodes" in {e["code"] for e in response.json()["errors"]}


def test_publishing_an_episode_without_artwork_is_refused(api, editor_headers, db, show):
    episode = _episode(db, show, 1)
    response = api.patch(
        f"/admin/episodes/{episode.id}", headers=editor_headers, json={"status": "published"}
    )
    assert response.status_code == 422
    assert "episode_missing_artwork" in {e["code"] for e in response.json()["errors"]}


def test_publishing_an_episode_without_duration_is_refused(api, editor_headers, db, show):
    episode = _episode(db, show, 2, duration_seconds=None)
    _add_thumbnail(db, episode.id)
    response = api.patch(
        f"/admin/episodes/{episode.id}", headers=editor_headers, json={"status": "published"}
    )
    assert response.status_code == 422
    assert "episode_missing_duration" in {e["code"] for e in response.json()["errors"]}


def test_publishing_a_complete_episode_succeeds(api, editor_headers, db, show):
    episode = _episode(db, show, 3)
    _add_thumbnail(db, episode.id)
    response = api.patch(
        f"/admin/episodes/{episode.id}", headers=editor_headers, json={"status": "published"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "published"


def test_duplicate_content_group_and_language_is_a_readable_conflict(api, editor_headers, show):
    body = {
        "season_id": show.seasons[0].id,
        "episode_number": 9,
        "title": "Dup",
        "duration_seconds": 300,
        "language": "hi",
        "content_group": "alpha-s01e09",
    }
    assert api.post("/admin/episodes", headers=editor_headers, json=body).status_code == 201
    second = api.post(
        "/admin/episodes", headers=editor_headers, json={**body, "episode_number": 10}
    )
    assert second.status_code == 409
    error = second.json()["errors"][0]
    assert error["code"] == "duplicate_language_variant"
    assert "hi" in error["message"]


def test_the_other_language_of_the_same_group_is_allowed(api, editor_headers, show):
    body = {
        "season_id": show.seasons[0].id,
        "episode_number": 9,
        "title": "Pair",
        "duration_seconds": 300,
        "language": "en",
        "content_group": "alpha-s01e09",
    }
    assert api.post("/admin/episodes", headers=editor_headers, json=body).status_code == 201
    second = api.post("/admin/episodes", headers=editor_headers, json={**body, "language": "hi"})
    assert second.status_code == 201


def test_unknown_language_is_rejected(api, editor_headers, show):
    response = api.post(
        "/admin/episodes",
        headers=editor_headers,
        json={
            "season_id": show.seasons[0].id,
            "episode_number": 1,
            "title": "T",
            "duration_seconds": 300,
            "language": "fr",
            "content_group": "alpha-s01e01",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "unknown_language"


def test_show_list_filters_compose(api, editor_headers, db):
    db.add_all(
        [
            Show(
                slug="a", title="Aa", section="series", synopsis="",
                categories=["music"], status=ContentStatus.published,
            ),
            Show(
                slug="b", title="Bb", section="songs", synopsis="",
                categories=["music"], status=ContentStatus.draft,
            ),
            Show(
                slug="c", title="Cc", section="series", synopsis="",
                categories=["music"], status=ContentStatus.draft,
            ),
        ]
    )
    db.flush()
    response = api.get("/admin/shows?section=series&status=published", headers=editor_headers)
    assert [item["slug"] for item in response.json()["items"]] == ["a"]


def test_show_list_paginates(api, editor_headers, db):
    for i in range(25):
        db.add(Show(slug=f"s{i:02d}", title=f"S{i:02d}", synopsis="", categories=[]))
    db.flush()
    body = api.get("/admin/shows?page=2&page_size=10", headers=editor_headers).json()
    assert body["total"] == 25
    assert len(body["items"]) == 10
    assert body["page"] == 2


def test_episode_list_filters_by_show_and_language(api, editor_headers, db, show):
    _episode(db, show, 1, language="en", content_group="alpha-s01e01")
    _episode(db, show, 1, language="hi", content_group="alpha-s01e01")
    body = api.get(
        f"/admin/episodes?show_id={show.id}&language=hi", headers=editor_headers
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["language"] == "hi"


def test_missing_required_field_uses_the_shared_error_envelope(api, editor_headers):
    """FastAPI's own validation errors must not leak a second response shape."""
    response = api.post("/admin/shows", headers=editor_headers, json={"title": "No slug"})
    assert response.status_code == 422
    body = response.json()
    assert "errors" in body and "detail" not in body
    assert body["errors"][0]["field"] == "slug"
    assert body["errors"][0]["message"] == "This is required."
