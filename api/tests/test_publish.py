import pytest

from app.catalog.publish import PublishBlocked, publish
from app.models import CatalogPointer, Episode, RunStatus, Show
from app.seed import seed


@pytest.fixture
def seeded(db, storage):
    seed(db, storage)
    db.flush()


def _catalog_files(storage):
    return list((storage.root / "catalog" / "runs").glob("*.json"))


def _edit_something(db):
    db.query(Show).filter_by(slug="curious-cubs").one().title = "Curious Cubs Returns"
    db.flush()


def test_publish_writes_a_run_scoped_file_and_flips_the_pointer(db, storage, seeded, users):
    run = publish(db, storage, users["admin"].id)
    assert run.status == RunStatus.success
    assert run.catalog_key == f"catalog/runs/{run.run_id}.json"
    assert storage.exists(run.catalog_key)
    assert db.get(CatalogPointer, 1).current_run_id == run.id


def test_publish_never_overwrites_an_existing_file(db, storage, seeded, users):
    """Two publishes over changed data must produce two files, not one."""
    first = publish(db, storage, users["admin"].id)
    _edit_something(db)
    second = publish(db, storage, users["admin"].id)

    assert first.catalog_key != second.catalog_key
    assert storage.exists(first.catalog_key), "the previous catalogue must survive"
    assert storage.exists(second.catalog_key)
    assert len(_catalog_files(storage)) == 2


def test_publishing_twice_with_no_edits_records_no_change(db, storage, seeded, users):
    first = publish(db, storage, users["admin"].id)
    second = publish(db, storage, users["admin"].id)
    assert second.status == RunStatus.no_change
    assert second.catalog_key is None
    assert second.content_hash == first.content_hash
    assert len(_catalog_files(storage)) == 1


def test_the_pointer_does_not_move_on_a_no_change_run(db, storage, seeded, users):
    first = publish(db, storage, users["admin"].id)
    publish(db, storage, users["admin"].id)
    assert db.get(CatalogPointer, 1).current_run_id == first.id


def test_publish_records_counts_and_author(db, storage, seeded, users):
    run = publish(db, storage, users["admin"].id)
    assert run.started_by == users["admin"].id
    assert run.counts["shows"] == 7
    assert run.counts["episodes"] > 0
    assert run.counts["trailers"] == 2
    assert run.finished_at is not None


def test_blocking_validation_prevents_any_write(db, storage, seeded, users):
    episode = db.query(Episode).filter_by(content_group="motis-many-lives-s01e01").first()
    episode.duration_seconds = None
    db.flush()

    with pytest.raises(PublishBlocked) as exc:
        publish(db, storage, users["admin"].id)

    assert exc.value.run.status == RunStatus.failed
    assert _catalog_files(storage) == []
    assert db.get(CatalogPointer, 1).current_run_id is None
    codes = {
        issue["code"] for group in exc.value.report["groups"] for issue in group["blocking"]
    }
    assert "episode_missing_duration" in codes


def test_a_crash_before_the_pointer_flip_leaves_readers_untouched(
    db, storage, seeded, users, monkeypatch
):
    """The new file may land, but until the pointer moves nothing can reach it.

    This is the atomicity claim itself, not a proxy for it.
    """
    from app.catalog import publish as publish_module

    first = publish_module.publish(db, storage, users["admin"].id)
    assert db.get(CatalogPointer, 1).current_run_id == first.id

    _edit_something(db)

    def explode(*_args, **_kwargs):
        raise RuntimeError("process died after the write")

    monkeypatch.setattr(publish_module, "_flip_pointer", explode)
    with pytest.raises(RuntimeError):
        publish_module.publish(db, storage, users["admin"].id)

    # An orphan file exists, and is unreachable because nothing points at it.
    assert len(_catalog_files(storage)) == 2
    assert db.get(CatalogPointer, 1).current_run_id == first.id


def test_publish_route_rejects_an_editor(api, storage, seeded, editor_headers, monkeypatch):
    from app.routers import admin_catalog

    monkeypatch.setattr(admin_catalog, "get_storage", lambda: storage)
    response = api.post("/admin/catalog/publish", headers=editor_headers)
    assert response.status_code == 403
    assert response.json()["errors"][0]["code"] == "forbidden"
    assert _catalog_files(storage) == []


def test_publish_route_rejects_an_anonymous_caller(api, storage, seeded):
    assert api.post("/admin/catalog/publish").status_code == 401


def test_publish_route_allows_an_admin(api, storage, seeded, admin_headers, monkeypatch):
    from app.routers import admin_catalog

    monkeypatch.setattr(admin_catalog, "get_storage", lambda: storage)
    response = api.post("/admin/catalog/publish", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_blocked_publish_returns_409_with_the_reasons(
    api, db, storage, seeded, admin_headers, monkeypatch
):
    from app.routers import admin_catalog

    monkeypatch.setattr(admin_catalog, "get_storage", lambda: storage)
    episode = db.query(Episode).filter_by(content_group="motis-many-lives-s01e01").first()
    episode.duration_seconds = None
    db.flush()

    response = api.post("/admin/catalog/publish", headers=admin_headers)
    assert response.status_code == 409
    body = response.json()
    assert body["report"]["can_publish"] is False
    assert body["errors"][0]["code"] == "publish_blocked"


def test_run_history_is_newest_first(api, db, storage, seeded, admin_headers, monkeypatch):
    from app.routers import admin_catalog

    monkeypatch.setattr(admin_catalog, "get_storage", lambda: storage)
    publish(db, storage, None)
    _edit_something(db)
    publish(db, storage, None)

    body = api.get("/admin/catalog/runs", headers=admin_headers).json()
    assert len(body["items"]) == 2
    assert body["items"][0]["started_at"] >= body["items"][1]["started_at"]
    assert body["items"][0]["id"] > body["items"][1]["id"]


def test_run_history_is_visible_to_an_editor(api, db, storage, seeded, editor_headers):
    publish(db, storage, None)
    response = api.get("/admin/catalog/runs", headers=editor_headers)
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


def test_sweep_fails_runs_abandoned_by_a_dead_process(db):
    import uuid
    from datetime import UTC, datetime, timedelta

    from app.catalog.publish import sweep_stale_runs
    from app.models import PublishRun

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
