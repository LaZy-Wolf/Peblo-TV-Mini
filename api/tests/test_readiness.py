import pytest

from app.catalog.publish import publish
from app.catalog.serve import invalidate_cache
from app.seed import seed


@pytest.fixture(autouse=True)
def clean_cache():
    invalidate_cache()
    yield
    invalidate_cache()


@pytest.fixture
def probe(api, storage, monkeypatch):
    from app.routers import health

    monkeypatch.setattr(health, "get_storage", lambda: storage)
    return api


def test_healthz_touches_no_dependency(client):
    """Liveness must stay green even when the database is unreachable.

    Otherwise a database blip makes the orchestrator kill healthy containers,
    which turns a small incident into an outage.
    """
    assert client.get("/healthz").json() == {"status": "ok"}


def test_readyz_is_degraded_before_a_publish(probe, db):
    response = probe.get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"] is True
    assert body["checks"]["storage"] is True
    assert body["checks"]["catalog"] is False


def test_readyz_is_ready_after_a_publish(probe, db, storage, users):
    seed(db, storage)
    db.flush()
    publish(db, storage, users["admin"].id)
    invalidate_cache()

    response = probe.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert all(body["checks"].values())


def test_readyz_is_degraded_when_the_live_file_vanishes(probe, db, storage, users):
    """The alerting story: the pointer resolves but the file does not."""
    seed(db, storage)
    db.flush()
    run = publish(db, storage, users["admin"].id)
    storage.delete(run.catalog_key)
    invalidate_cache()

    body = probe.get("/readyz").json()
    assert body["status"] == "degraded"
    assert body["checks"]["catalog"] is False
