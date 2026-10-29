"""Object storage abstraction. Local disk for the prototype — NOT durable in a cloud container;
production must swap in managed object storage (S3/GCS) behind this same interface."""
from pathlib import Path

from ..config import get_settings


class LocalStorage:
    def __init__(self):
        self.root = Path(get_settings().storage_dir)

    def save(self, key: str, data: bytes) -> str:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("invalid storage key")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("invalid storage key")
        return path


def get_storage() -> LocalStorage:
    return LocalStorage()
