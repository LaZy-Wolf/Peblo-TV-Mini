from pathlib import Path

import pytest

from app.config import settings
from app.models import Artwork, Season, Show

ASSETS = Path(settings.data_dir) / "assets"


@pytest.fixture
def show(db):
    record = Show(slug="s", title="S", synopsis="", section="series", categories=["music"])
    db.add(record)
    db.flush()
    db.add(Season(show_id=record.id, season_number=1))
    db.flush()
    return record


@pytest.fixture(autouse=True)
def local_storage(monkeypatch, storage):
    from app.routers import artwork as artwork_router

    monkeypatch.setattr(artwork_router, "get_storage", lambda: storage)
    return storage


def _upload(api, headers, kind, filename, **owner):
    return api.post(
        "/admin/artwork",
        headers=headers,
        data={"kind": kind, **{k: str(v) for k, v in owner.items()}},
        files={"file": (filename, (ASSETS / filename).read_bytes(), "image/jpeg")},
    )


def test_upload_good_poster_creates_a_record(api, db, editor_headers, show, storage):
    response = _upload(api, editor_headers, "poster", "poster_good.jpg", show_id=show.id)
    assert response.status_code == 201
    body = response.json()
    assert (body["width"], body["height"]) == (600, 900)
    assert body["url"].startswith("http://t/media/")
    assert db.query(Artwork).filter_by(show_id=show.id, kind="poster").count() == 1


def test_rejected_upload_writes_nothing_to_storage(api, db, editor_headers, show, storage):
    """Validation runs before storage, so a rejection leaves no orphan file."""
    response = _upload(api, editor_headers, "poster", "poster_wrong_ratio.jpg", show_id=show.id)
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "artwork_wrong_aspect"
    assert list(storage.root.rglob("*.jpg")) == []
    assert db.query(Artwork).count() == 0


def test_oversized_upload_is_refused(api, editor_headers, show):
    response = _upload(api, editor_headers, "banner", "banner_too_big.png", show_id=show.id)
    assert response.status_code == 422
    codes = {e["code"] for e in response.json()["errors"]}
    assert "artwork_wrong_dimensions" in codes


def test_upload_requires_authentication(api, show):
    response = api.post(
        "/admin/artwork",
        data={"kind": "poster", "show_id": str(show.id)},
        files={"file": ("p.jpg", (ASSETS / "poster_good.jpg").read_bytes(), "image/jpeg")},
    )
    assert response.status_code == 401


def test_upload_requires_exactly_one_owner(api, editor_headers):
    response = api.post(
        "/admin/artwork",
        headers=editor_headers,
        data={"kind": "poster"},
        files={"file": ("p.jpg", (ASSETS / "poster_good.jpg").read_bytes(), "image/jpeg")},
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "artwork_missing_owner"


def test_upload_rejects_both_owners_at_once(api, editor_headers, show):
    response = api.post(
        "/admin/artwork",
        headers=editor_headers,
        data={"kind": "poster", "show_id": str(show.id), "episode_id": "1"},
        files={"file": ("p.jpg", (ASSETS / "poster_good.jpg").read_bytes(), "image/jpeg")},
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "artwork_missing_owner"


def test_upload_for_a_missing_show_is_a_404(api, editor_headers):
    response = _upload(api, editor_headers, "poster", "poster_good.jpg", show_id=999999)
    assert response.status_code == 404


def test_uploading_the_same_slot_twice_replaces_it(api, db, editor_headers, show):
    """An editor re-uploading a corrected image should not have to delete first."""
    for _ in range(2):
        response = _upload(api, editor_headers, "poster", "poster_good.jpg", show_id=show.id)
        assert response.status_code == 201
    assert db.query(Artwork).filter_by(show_id=show.id, kind="poster").count() == 1


def test_delete_removes_the_record(api, db, editor_headers, show):
    created = _upload(api, editor_headers, "poster", "poster_good.jpg", show_id=show.id).json()
    assert api.delete(f"/admin/artwork/{created['id']}", headers=editor_headers).status_code == 204
    assert db.query(Artwork).count() == 0
