from typing import Protocol


class Storage(Protocol):
    """The only storage surface the rest of the application may depend on.

    Moving from local disk to Cloudflare R2 is a change of implementation and
    environment variables, never a change of call site.
    """

    def put(self, key: str, data: bytes, content_type: str) -> str:
        """Write bytes at key. Returns the public URL."""
        ...

    def get(self, key: str) -> bytes: ...

    def url(self, key: str) -> str: ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None: ...


class ObjectNotFound(Exception):
    pass
