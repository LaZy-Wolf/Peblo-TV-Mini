"""One contract, run against both storage backends.

The point of the Storage Protocol is that swapping local disk for Cloudflare
R2 is a change of implementation, not of behaviour. Asserting that in prose is
cheap; this runs the same assertions against both.

R2Storage is exercised against MinIO, which speaks the same S3 API R2 does, so
the boto3 calls execute over the wire rather than only being written. That is
not the same as running against Cloudflare, and the README says so.

Start MinIO with:  docker compose --profile storage-test up -d minio
"""

import os
import uuid

import pytest

from app.storage import LocalDiskStorage, ObjectNotFound, R2Storage

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_KEY = os.environ.get("MINIO_ACCESS_KEY", "peblo")
MINIO_SECRET = os.environ.get("MINIO_SECRET_KEY", "peblo-dev-secret")


def _minio_storage() -> R2Storage:
    """An R2Storage pointed at MinIO, with its bucket created."""
    bucket = f"peblo-test-{uuid.uuid4().hex[:12]}"
    storage = R2Storage(
        account_id="unused-when-endpoint-is-given",
        access_key_id=MINIO_KEY,
        secret_access_key=MINIO_SECRET,
        bucket=bucket,
        endpoint_url=MINIO_ENDPOINT,
        public_base_url="http://minio.test/media",
    )
    storage.client.create_bucket(Bucket=bucket)
    return storage


def _minio_or_skip() -> R2Storage:
    boto_error = pytest.importorskip("botocore.exceptions")
    try:
        return _minio_storage()
    except (boto_error.EndpointConnectionError, OSError) as exc:
        pytest.skip(
            f"MinIO is not reachable at {MINIO_ENDPOINT}. "
            f"Start it with: docker compose --profile storage-test up -d minio ({exc})"
        )


@pytest.fixture(params=["local", "r2"])
def storage_backend(request, tmp_path):
    if request.param == "local":
        return LocalDiskStorage(tmp_path, "http://example.test/media")
    return _minio_or_skip()


def test_put_then_get_roundtrips(storage_backend):
    storage_backend.put("a/b/c.jpg", b"hello", "image/jpeg")
    assert storage_backend.get("a/b/c.jpg") == b"hello"


def test_put_returns_the_public_url(storage_backend):
    url = storage_backend.put("k.jpg", b"x", "image/jpeg")
    assert url.endswith("/media/k.jpg")


def test_exists_reflects_reality(storage_backend):
    assert storage_backend.exists("nope.jpg") is False
    storage_backend.put("yes.jpg", b"x", "image/jpeg")
    assert storage_backend.exists("yes.jpg") is True


def test_get_missing_raises_object_not_found(storage_backend):
    """Both backends must raise the same exception, or callers cannot be
    written once. This is the assertion most likely to catch a real swap bug."""
    with pytest.raises(ObjectNotFound):
        storage_backend.get("missing.jpg")


def test_delete_is_idempotent(storage_backend):
    storage_backend.put("d.jpg", b"x", "image/jpeg")
    storage_backend.delete("d.jpg")
    storage_backend.delete("d.jpg")
    assert storage_backend.exists("d.jpg") is False


def test_overwriting_a_key_replaces_its_contents(storage_backend):
    storage_backend.put("o.jpg", b"first", "image/jpeg")
    storage_backend.put("o.jpg", b"second", "image/jpeg")
    assert storage_backend.get("o.jpg") == b"second"


def test_a_catalogue_sized_json_payload_roundtrips(storage_backend):
    """The publish path writes JSON, not just small images."""
    payload = (b'{"version":1,"sections":[]}' * 5000)
    storage_backend.put("catalog/runs/x.json", payload, "application/json")
    assert storage_backend.get("catalog/runs/x.json") == payload


def test_nested_keys_work(storage_backend):
    """Local disk needs directories created; S3 has no directories at all.
    Both must accept the same key shape the application actually uses."""
    key = "artwork/shows/12/poster-abc123def456.jpg"
    storage_backend.put(key, b"img", "image/jpeg")
    assert storage_backend.exists(key) is True
    assert storage_backend.get(key) == b"img"


def test_the_whole_publish_pipeline_runs_on_s3(db):
    """The strongest version of the claim.

    Not just that R2Storage satisfies the Protocol, but that seeding, artwork
    upload, catalogue build and publish all work unchanged when the backend is
    swapped for S3. If "swapping should be one class" is true, this passes
    with no application code touched.
    """
    import json

    from app.catalog.publish import publish
    from app.models import RunStatus
    from app.seed import seed

    storage = _minio_or_skip()

    result = seed(db, storage)
    db.flush()
    assert result.shows == 8
    assert result.artwork == 117, "artwork went through validation and onto S3"

    run = publish(db, storage, None)
    assert run.status == RunStatus.success
    assert run.catalog_key.startswith("catalog/runs/")

    # Read the published catalogue back off S3 the way the viewer would.
    catalog = json.loads(storage.get(run.catalog_key))
    assert catalog["hero"]["slug"] == "motis-many-lives"
    assert [s["key"] for s in catalog["sections"]] == [
        "featured",
        "series",
        "minisodes",
        "songs",
    ]
    assert run.counts["shows"] == 7

    # Artwork URLs point at the S3 public base, not at local disk.
    shows = [s for section in catalog["sections"] for s in section["shows"]]
    moti = next(s for s in shows if s["slug"] == "motis-many-lives")
    assert moti["artwork"]["poster"].startswith("http://minio.test/media/")


def test_publishing_twice_on_s3_is_still_idempotent(db):
    """Idempotence comes from the content hash, not from the filesystem, so it
    must survive the backend swap."""
    from app.catalog.publish import publish
    from app.models import RunStatus
    from app.seed import seed

    storage = _minio_or_skip()
    seed(db, storage)
    db.flush()

    first = publish(db, storage, None)
    second = publish(db, storage, None)
    assert first.status == RunStatus.success
    assert second.status == RunStatus.no_change
    assert second.catalog_key is None
