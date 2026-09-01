from pathlib import Path

from app.storage.base import ObjectNotFound


class LocalDiskStorage:
    def __init__(self, root: Path | str, public_base_url: str):
        self.root = Path(root)
        self.public_base_url = public_base_url.rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError("key escapes storage root")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return self.url(key)

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise ObjectNotFound(key)
        return path.read_bytes()

    def url(self, key: str) -> str:
        return f"{self.public_base_url}/{key}"

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
