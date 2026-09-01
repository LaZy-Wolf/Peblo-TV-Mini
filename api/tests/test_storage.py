import inspect

import pytest

from app.storage import LocalDiskStorage, ObjectNotFound, R2Storage


@pytest.fixture
def disk(tmp_path):
    return LocalDiskStorage(tmp_path, "http://example.test/media")


def test_put_then_get_roundtrips(disk):
    disk.put("a/b/c.jpg", b"hello", "image/jpeg")
    assert disk.get("a/b/c.jpg") == b"hello"


def test_put_returns_public_url(disk):
    assert disk.put("k.jpg", b"x", "image/jpeg") == "http://example.test/media/k.jpg"


def test_exists_reflects_reality(disk):
    assert disk.exists("nope.jpg") is False
    disk.put("yes.jpg", b"x", "image/jpeg")
    assert disk.exists("yes.jpg") is True


def test_get_missing_raises(disk):
    with pytest.raises(ObjectNotFound):
        disk.get("missing.jpg")


def test_delete_is_idempotent(disk):
    disk.put("d.jpg", b"x", "image/jpeg")
    disk.delete("d.jpg")
    disk.delete("d.jpg")
    assert disk.exists("d.jpg") is False


def test_key_cannot_escape_the_root(disk):
    with pytest.raises(ValueError):
        disk.put("../escape.jpg", b"x", "image/jpeg")


def test_both_backends_expose_the_same_signatures():
    """Constructed with nothing and never called, so no network.

    This exists so a signature drifting apart between the two implementations
    fails here rather than the first time someone flips STORAGE_BACKEND.
    """
    for name in ("put", "get", "url", "exists", "delete"):
        local_sig = inspect.signature(getattr(LocalDiskStorage, name))
        r2_sig = inspect.signature(getattr(R2Storage, name))
        assert list(local_sig.parameters) == list(r2_sig.parameters), name
