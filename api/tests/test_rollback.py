import uuid

import pytest

from app.catalog.publish import publish, rollback
from app.catalog.serve import invalidate_cache
from app.errors import ApiException
from app.models import CatalogPointer, PublishRun, RunStatus, Show
from app.seed import seed


@pytest.fixture(autouse=True)
def clean_cache():
    invalidate_cache()
    yield
    invalidate_cache()


@pytest.fixture
def two_runs(db, storage, users):
    seed(db, storage)
    db.flush()
    first = publish(db, storage, users["admin"].id)
    db.query(Show).filter_by(slug="curious-cubs").one().title = "Curious Cubs Returns"
    db.flush()
    second = publish(db, storage, users["admin"].id)
    return first, second


def test_rollback_moves_the_pointer_back(db, storage, two_runs):
    first, second = two_runs
    assert db.get(CatalogPointer, 1).current_run_id == second.id
    rollback(db, storage, first.id)
    assert db.get(CatalogPointer, 1).current_run_id == first.id


def test_rollback_serves_the_older_catalogue(db, storage, two_runs, api, monkeypatch):
    """The whole point: the previous file was never destroyed."""
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


def test_rollback_to_a_failed_run_is_refused(db, storage, two_runs):
    bad = PublishRun(run_id=uuid.uuid4(), status=RunStatus.failed)
    db.add(bad)
    db.flush()
    with pytest.raises(ApiException) as exc:
        rollback(db, storage, bad.id)
    assert exc.value.errors[0].code == "rollback_invalid_target"


def test_rollback_to_a_missing_run_is_refused(db, storage, two_runs):
    with pytest.raises(ApiException) as exc:
        rollback(db, storage, 999999)
    assert exc.value.errors[0].code == "rollback_invalid_target"


def test_rollback_when_the_file_is_gone_is_refused(db, storage, two_runs):
    first, _ = two_runs
    storage.delete(first.catalog_key)
    with pytest.raises(ApiException) as exc:
        rollback(db, storage, first.id)
    assert exc.value.errors[0].code == "rollback_file_missing"


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


def test_publishing_after_a_rollback_writes_a_new_run(db, storage, two_runs, users):
    """Rolling back must not strand the system on an old run forever."""
    first, _ = two_runs
    rollback(db, storage, first.id)
    db.query(Show).filter_by(slug="curious-cubs").one().title = "Third Title"
    db.flush()
    third = publish(db, storage, users["admin"].id)
    assert third.status == RunStatus.success
    assert db.get(CatalogPointer, 1).current_run_id == third.id
