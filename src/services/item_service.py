"""Domain business logic for managing lost and found items.

Handles:
- Image validation (MIME types, size limits, corruption detection)
- File storage for image blobs
- Coordination with AIService (VLM extraction + embeddings)
- Item registration, listing, and top-k similarity matching
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np

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

logger = logging.getLogger(__name__)

# Allowed MIME types and image magic headers
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png"}
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class ItemServiceError(Exception):
    """Base exception for ItemService errors."""


class ItemNotFoundError(ItemServiceError):
    """Raised when an item ID does not exist."""


class InvalidImageError(ItemServiceError):
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
            f"Image size ({len(data)} bytes) exceeds the {settings.MAX_IMAGE_SIZE_MB}MB limit ({max_bytes} bytes)"
        )

    # Magic byte header check
    if data.startswith(JPEG_MAGIC):
        mime_type = "image/jpeg"
    elif data.startswith(PNG_MAGIC):
        mime_type = "image/png"
    else:
        raise InvalidImageError(
            f"Unsupported image format for '{filename}'. Only JPEG and PNG are allowed."
        )

    # Corruption / truncation check
    if mime_type == "image/jpeg":
        if len(data) < 4 or (b"\xff\xd9" not in data[-10:] and b"\xff\xd9" not in data):
            raise CorruptImageError(
                "Corrupt or truncated JPEG image: missing EOF marker"
            )
    elif mime_type == "image/png":
        if len(data) < 24:
            raise CorruptImageError(
                "Corrupt PNG image: file too small to contain valid headers"
            )

    return mime_type


def generate_match_reason(query: ItemDescription, candidate: ItemDescription) -> str:
    """Generate human-readable explanation for why two items matched."""
    reasons: list[str] = []

    if query.object_class.lower() == candidate.object_class.lower():
        reasons.append(f"Identical category: {query.object_class}")
    else:
        reasons.append(f"Categories: {query.object_class} ~ {candidate.object_class}")

    common_colors = set(c.lower() for c in query.colors) & set(
        c.lower() for c in candidate.colors
    )
    if common_colors:
        reasons.append(f"Matching color(s): {', '.join(sorted(common_colors))}")

    if query.brand and candidate.brand:
        if query.brand.lower() == candidate.brand.lower():
            reasons.append(f"Matching brand: {query.brand}")

    return "; ".join(reasons) if reasons else "High visual and textual similarity"


class ItemService:
    """Core domain service for item management and similarity matching."""

    def __init__(
        self,
        storage_dir: Path | str | None = None,
        ai_service: AIService | None = None,
    ):
        self.storage_dir = Path(storage_dir or settings.IMAGE_STORAGE_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.ai_service = ai_service or AIService()

        # In-memory storage repository (easily swappable with database)
        # TODO (Task 3 - Storage): Replace this in-memory dict with self.repository: ItemRepository from src.storage.repository (PostgreSQL/AsyncPG)
        self._items: dict[str, ItemRecord] = {}

    def register_item(
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
        mime = validate_image_bytes(image_bytes, filename=filename)
        ext = ".jpg" if mime == "image/jpeg" else ".png"

        item_id = str(uuid4())
        safe_filename = f"{item_id}{ext}"
        saved_image_path = self.storage_dir / safe_filename

        # Persist image blob to filesystem
        saved_image_path.write_bytes(image_bytes)

        # Call AI Service for VLM analysis
        try:
            description = self.ai_service.describe_item(
                str(saved_image_path),
                user_text,
                vlm=vlm,
            )
        except Exception as exc:
            if saved_image_path.exists():
                saved_image_path.unlink()
            raise ItemServiceError(
                f"Failed to analyze item image with VLM: {exc}"
            ) from exc

        # Generate search embedding
        search_text = description.to_search_text()
        try:
            embedding_vec = self.ai_service.get_embedding(
                search_text, embedder=embedder
            )
        except Exception as exc:
            if saved_image_path.exists():
                saved_image_path.unlink()
            raise ItemServiceError(f"Failed to generate embedding: {exc}") from exc

        # Create ItemRecord and persist
        record = ItemRecord(
            id=item_id,
            status=status,
            user_text=user_text,
            image_path=str(saved_image_path),
            description=description,
            embedding=embedding_vec.tolist(),
        )
        # TODO (Task 3 - Storage): Replace dictionary assignment with self.repository.save(record)
        self._items[item_id] = record
        logger.info("Registered %s item with ID: %s", status.value, item_id)
        return record

    def get_item(self, item_id: str) -> ItemRecord:
        """Fetch item by ID or raise ItemNotFoundError."""
        # TODO (Task 3 - Storage): Replace dictionary lookup with self.repository.get_by_id(item_id)
        if item_id not in self._items:
            raise ItemNotFoundError(f"Item with ID '{item_id}' not found")
        return self._items[item_id]

    def list_items(self, status: ItemStatus | None = None) -> list[ItemRecord]:
        """List items, optionally filtered by status, sorted latest first."""
        # TODO (Task 3 - Storage): Replace in-memory list with self.repository.list_all(status)
        items = list(self._items.values())
        if status is not None:
            items = [item for item in items if item.status == status]
        items.sort(key=lambda x: x.created_at, reverse=True)
        return items

    def find_matches(self, item_id: str, k: int = 3) -> MatchQueryResponse:
        """Find top-k matches from the opposite pool using cosine similarity."""
        query_item = self.get_item(item_id)
        target_status = (
            ItemStatus.FOUND
            if query_item.status == ItemStatus.LOST
            else ItemStatus.LOST
        )

        # TODO (Task 3 - Storage): Query candidates from repository via self.repository.list_by_status(target_status)
        # TODO (Task 4 - Concurrency): If candidate pool is large, parallelize batch similarity scoring
        candidates = [
            item
            for item in self._items.values()
            if item.status == target_status and item.embedding is not None
        ]

        query_response = ItemResponse(
            id=query_item.id,
            status=query_item.status,
            user_text=query_item.user_text,
            image_path=query_item.image_path,
            description=query_item.description,
            created_at=query_item.created_at,
        )

        if not candidates or query_item.embedding is None:
            return MatchQueryResponse(
                query_item=query_response,
                matches=[],
                total_candidates_evaluated=0,
            )

        query_vec = np.asarray(query_item.embedding, dtype=np.float32)
        cand_vecs = [np.asarray(c.embedding, dtype=np.float32) for c in candidates]

        match_results = ai.top_k(query_vec, cand_vecs, k=k)

        matches: list[MatchItem] = []
        for res in match_results:
            cand = candidates[res.candidate_id]
            reason = generate_match_reason(query_item.description, cand.description)
            cand_resp = ItemResponse(
                id=cand.id,
                status=cand.status,
                user_text=cand.user_text,
                image_path=cand.image_path,
                description=cand.description,
                created_at=cand.created_at,
            )
            matches.append(MatchItem(item=cand_resp, score=res.score, reason=reason))

        return MatchQueryResponse(
            query_item=query_response,
            matches=matches,
            total_candidates_evaluated=len(candidates),
        )
