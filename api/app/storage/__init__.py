from functools import lru_cache

from app.config import settings
from app.storage.base import ObjectNotFound, Storage
from app.storage.local import LocalDiskStorage
from app.storage.r2 import R2Storage

__all__ = ["LocalDiskStorage", "ObjectNotFound", "R2Storage", "Storage", "get_storage"]


@lru_cache
def get_storage() -> Storage:
    """The single place the backend choice is made. One env var swaps it."""
    if settings.storage_backend == "r2":
        return R2Storage(
            account_id=settings.r2_account_id,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            bucket=settings.r2_bucket,
            endpoint_url=settings.r2_endpoint_url,
            public_base_url=settings.storage_public_base_url,
        )
    return LocalDiskStorage(settings.storage_local_root, settings.storage_public_base_url)
