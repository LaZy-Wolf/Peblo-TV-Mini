"""Local-disk specifics and cross-backend signature parity.

The shared behaviour both backends must exhibit lives in
test_storage_contract.py, which runs the same assertions against each.
"""

import inspect

import pytest

from app.storage import LocalDiskStorage, R2Storage


@pytest.fixture
def disk(tmp_path):
    return LocalDiskStorage(tmp_path, "http://example.test/media")


def test_public_url_is_the_base_plus_the_key(disk):
    assert disk.put("k.jpg", b"x", "image/jpeg") == "http://example.test/media/k.jpg"


def test_a_key_cannot_escape_the_storage_root(disk):
    """Only local disk has a filesystem to escape from. S3 keys are opaque."""
    with pytest.raises(ValueError):
        disk.put("../escape.jpg", b"x", "image/jpeg")


def test_deeply_nested_keys_create_their_directories(disk):
    disk.put("a/b/c/d/e.jpg", b"x", "image/jpeg")
    assert (disk.root / "a" / "b" / "c" / "d" / "e.jpg").exists()


def test_both_backends_expose_the_same_signatures():
    """Constructed with nothing and never called, so no network.

    A signature drifting apart between the two implementations fails here
    rather than the first time someone flips STORAGE_BACKEND in production.
    """
    for name in ("put", "get", "url", "exists", "delete"):
        local_sig = inspect.signature(getattr(LocalDiskStorage, name))
        r2_sig = inspect.signature(getattr(R2Storage, name))
        assert list(local_sig.parameters) == list(r2_sig.parameters), name
