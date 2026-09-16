from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from src.config import settings


class ImageStorage:
    """Filesystem storage for uploaded item images."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or settings.IMAGE_STORAGE_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, image_data: bytes, extension: str) -> str:
        """Save image bytes and return the relative image path."""
        filename = f"{uuid4()}{extension}"
        file_path = self.storage_dir / filename

        file_path.write_bytes(image_data)

        return str(file_path)

    def get(self, image_path: str) -> bytes:
        """Read an image from filesystem."""
        return Path(image_path).read_bytes()

    def delete(self, image_path: str) -> None:
        """Delete an image from filesystem if it exists."""
        path = Path(image_path)

        if path.exists():
            path.unlink()