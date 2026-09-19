"""Domain business logic for managing lost and found items.

Handles:
- Image validation (MIME types, size limits, corruption detection via Pillow)
- File storage for image blobs
- Coordination with AIService (VLM extraction + embeddings)
- Item registration, listing, and top-k similarity matching
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
from PIL import Image, UnidentifiedImageError

import ai
from ai.schemas import ItemDescription
from src.config import settings
from src.models import (
    ItemRecord,
    ItemResponse,
    ItemStatus,
    MatchItem,
    MatchQueryResponse,
)
from src.services.ai_service import AIService
from src.storage.image_storage import ImageStorage
from src.storage.repository import BaseItemRepository, PostgresItemRepository

logger = logging.getLogger(__name__)

# Allowed MIME types and image magic headers
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png"}
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class ItemManagerError(Exception):
    """Base exception for ItemManager errors."""


class ItemNotFoundError(ItemManagerError):
    """Raised when an item ID does not exist."""


class InvalidImageError(ItemManagerError):
    """Raised when an uploaded image fails validation."""


class ImageTooLargeError(InvalidImageError):
    """Raised when an uploaded image exceeds maximum allowed size."""


class CorruptImageError(InvalidImageError):
    """Raised when image bytes are malformed or corrupt."""


def validate_image_bytes(data: bytes, filename: str = "") -> str:
    """Validate image format, size, and integrity. Returns detected MIME type.

    Raises:
        ImageTooLargeError: If size exceeds configured max_image_size_bytes.
        InvalidImageError: If MIME type is not JPEG or PNG.
        CorruptImageError: If image bytes cannot be decoded or are corrupted.
    """
    if len(data) == 0:
        raise InvalidImageError("Image file is empty")

    max_bytes = settings.max_image_size_bytes
    if len(data) > max_bytes:
        raise ImageTooLargeError(
            f"Image size ({len(data)} bytes) exceeds the limit of "
            f"{settings.MAX_IMAGE_SIZE_MB}MB ({max_bytes} bytes)"
        )

    # 1. Magic byte header check
    if data.startswith(JPEG_MAGIC):
        mime_type = "image/jpeg"
    elif data.startswith(PNG_MAGIC):
        mime_type = "image/png"
    else:
        raise InvalidImageError(
            f"Unsupported image format for '{filename}'. "
            "Only JPEG and PNG are allowed."
        )

    # 2. EOF marker & structural minimum checks
    if mime_type == "image/jpeg":
        if len(data) < 4 or (
            b"\xff\xd9" not in data[-10:] and b"\xff\xd9" not in data
        ):
            raise CorruptImageError(
                "Corrupt or truncated JPEG image: missing EOF marker"
            )
    elif mime_type == "image/png":
        if len(data) < 24:
            raise CorruptImageError(
                "Corrupt PNG image: file too small to contain valid headers"
            )

    # 3. Deep decoding verification via Pillow
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()

            if mime_type == "image/jpeg" and img.format != "JPEG":
                raise CorruptImageError(
                    "MIME header says JPEG but internal image format does not match"
                )

            if mime_type == "image/png" and img.format != "PNG":
                raise CorruptImageError(
                    "MIME header says PNG but internal image format does not match"
                )

    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise CorruptImageError(
            f"Corrupt or unreadable image file: {exc}"
        ) from exc

    return mime_type


def generate_match_reason(
    query: ItemDescription,
    candidate: ItemDescription,
) -> str:
    """Generate human-readable explanation for why two items matched."""
    reasons: list[str] = []

    if query.object_class.lower() == candidate.object_class.lower():
        reasons.append(f"Identical category: {query.object_class}")
    else:
        reasons.append(
            f"Categories: {query.object_class} ~ {candidate.object_class}"
        )

    common_colors = set(c.lower() for c in query.colors) & set(
        c.lower() for c in candidate.colors
    )

    if common_colors:
        reasons.append(
            f"Matching color(s): {', '.join(sorted(common_colors))}"
        )

    if query.brand and candidate.brand:
        if query.brand.lower() == candidate.brand.lower():
            reasons.append(f"Matching brand: {query.brand}")

    return "; ".join(reasons) if reasons else "High visual and textual similarity"


class ItemManager:
    """Core domain manager for item management and similarity matching."""

    def __init__(
        self,
        storage_dir: Path | str | None = None,
        ai_service: AIService | None = None,
        repository: BaseItemRepository | None = None,
        image_storage: ImageStorage | None = None,
    ):
        self.ai_service = ai_service or AIService()

        self.repository = repository or PostgresItemRepository()

        self.image_storage = image_storage or ImageStorage(
            Path(storage_dir) if storage_dir else None
        )

    async def register_item(
            self,
            status: ItemStatus,
            image_bytes: bytes,
            filename: str,
            user_text: str,
            *,
            vlm: Any = None,
            embedder: Any = None,
    ) -> ItemRecord:
        """Validate, persist image blob, run AI extraction, and store item."""

        # 1. Validate image
        mime = validate_image_bytes(image_bytes, filename=filename)
        ext = ".jpg" if mime == "image/jpeg" else ".png"

        # 2. Save image to filesystem
        try:
            saved_image_path = self.image_storage.save(
                image_bytes,
                ext,
            )
        except OSError as exc:
            raise ItemManagerError(
                f"Failed to save image: {exc}"
            ) from exc

        # 3. Analyze image with VLM
        try:
            description = await self.ai_service.describe_item_async(
                saved_image_path,
                user_text,
                vlm=vlm,
            )
        except Exception as exc:
            self.image_storage.delete(saved_image_path)
            raise ItemManagerError(
                f"Failed to analyze item image with VLM: {exc}"
            ) from exc

        # 4. Generate search embedding
        search_text = description.to_search_text()

        try:
            embedding_vec = await self.ai_service.get_embedding_async(
                search_text,
                embedder=embedder,
            )
        except Exception as exc:
            self.image_storage.delete(saved_image_path)
            raise ItemManagerError(
                f"Failed to generate embedding: {exc}"
            ) from exc

        # 5. Create item record
        item_id = str(uuid4())

        record = ItemRecord(
            id=item_id,
            status=status,
            user_text=user_text,
            image_path=saved_image_path,
            description=description,
            embedding=embedding_vec.tolist(),
        )

        # 6. Persist metadata in PostgreSQL
        try:
            await self.repository.save(record)
        except Exception as exc:
            self.image_storage.delete(saved_image_path)
            raise ItemManagerError(
                f"Failed to save item to database: {exc}"
            ) from exc

        logger.info(
            "Registered %s item with ID: %s",
            status.value,
            item_id,
        )

        return record

    async def get_item(self, item_id: str) -> ItemRecord:
        item = await self.repository.get_by_id(item_id)

        if item is None:
            raise ItemNotFoundError(
                f"Item with ID '{item_id}' was not found."
            )

        return item

    async def list_items(
            self,
            status: ItemStatus | None = None,
    ) -> list[ItemRecord]:
        return await self.repository.list_all(status=status)

    async def find_matches(
            self,
            item_id: str,
            k: int = 3,
    ) -> MatchQueryResponse:
        """Find top-k matches from the opposite pool using cosine similarity."""
        query_item = await self.get_item(item_id)

        target_status = (
            ItemStatus.FOUND
            if query_item.status == ItemStatus.LOST
            else ItemStatus.LOST
        )

        candidates = await self.repository.list_all(status=target_status)

        candidates_with_embeddings = [
            item
            for item in candidates
            if item.embedding is not None
        ]

        if query_item.embedding is None:
            return MatchQueryResponse(
                query_item=ItemResponse.model_validate(query_item),
                matches=[],
                total_candidates_evaluated=len(candidates_with_embeddings),
            )

        query_vector = np.array(query_item.embedding, dtype=float)

        scored_candidates: list[tuple[ItemRecord, float]] = []

        for candidate in candidates_with_embeddings:
            candidate_vector = np.array(candidate.embedding, dtype=float)

            query_norm = np.linalg.norm(query_vector)
            candidate_norm = np.linalg.norm(candidate_vector)

            if query_norm == 0 or candidate_norm == 0:
                score = 0.0
            else:
                score = float(
                    np.dot(query_vector, candidate_vector)
                    / (query_norm * candidate_norm)
                )
                score = max(-1, min(1, score))

            scored_candidates.append((candidate, score))

        scored_candidates.sort(
            key=lambda pair: pair[1],
            reverse=True,
        )

        top_matches = scored_candidates[:k]

        matches = [
            MatchItem(
                item=ItemResponse(
                    id=candidate.id,
                    status=candidate.status,
                    user_text=candidate.user_text,
                    image_path=candidate.image_path,
                    description=candidate.description,
                    created_at=candidate.created_at,
                ),
                score=score,
                reason=generate_match_reason(
                    query_item.description,
                    candidate.description,
                ),
            )
            for candidate, score in top_matches
        ]

        return MatchQueryResponse(
            query_item=ItemResponse(
                id=query_item.id,
                status=query_item.status,
                user_text=query_item.user_text,
                image_path=query_item.image_path,
                description=query_item.description,
                created_at=query_item.created_at,
            ),
            matches=matches,
            total_candidates_evaluated=len(candidates_with_embeddings),
        )