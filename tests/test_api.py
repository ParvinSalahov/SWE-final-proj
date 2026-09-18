"""Tests for the FastAPI HTTP API (src/api.py).

All tests run offline: ItemManager is replaced with an AsyncMock so no
database, filesystem, or AI provider is contacted.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.models import ItemStatus, ItemResponse, MatchItem, MatchQueryResponse
from ai.schemas import ItemDescription
from src.core.item_manager import (
    CorruptImageError,
    ImageTooLargeError,
    InvalidImageError,
    ItemNotFoundError,
    ItemManagerError,
    ItemRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_item_record(
    status: ItemStatus = ItemStatus.LOST,
    item_id: str = "abc-123",
    user_text: str = "red wallet",
) -> ItemRecord:
    """Build a minimal ItemRecord for use in mocked responses."""
    desc = ItemDescription(
        object_class="wallet",
        colors=["red"],
        brand=None,
        distinguishing_marks=[],
        location_hints=[],
        confidence=0.9,
    )
    return ItemRecord(
        id=item_id,
        status=status,
        user_text=user_text,
        image_path="/tmp/img.jpg",
        description=desc,
        embedding=[0.1, 0.2],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _make_item_response(**kwargs: Any) -> ItemResponse:
    rec = _make_item_record(**kwargs)
    return ItemResponse(
        id=rec.id,
        status=rec.status,
        user_text=rec.user_text,
        image_path=rec.image_path,
        description=rec.description,
        created_at=rec.created_at,
    )


def _minimal_png() -> bytes:
    """Tiny valid 1×1 PNG bytes."""
    import struct, zlib

    def chunk(name: bytes, data: bytes) -> bytes:
        c = name + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    header = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = chunk(b"IHDR", ihdr_data)
    raw = b"\x00\xff\xff\xff"
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return header + ihdr + idat + iend


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_service():
    """Patch the global `service` in src.api with an AsyncMock."""
    with patch("src.api.service", new_callable=MagicMock) as svc:
        svc.register_item = AsyncMock()
        svc.find_matches = AsyncMock()
        svc.list_items = AsyncMock()
        yield svc


@pytest.fixture
def mock_create_tables():
    """Prevent DB setup from running during tests."""
    with patch("src.api.create_tables", new_callable=AsyncMock) as m:
        yield m


@pytest_asyncio.fixture
async def client(mock_service, mock_create_tables):
    """Async HTTP test client bound to the FastAPI app."""
    from src.api import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# GET /  — health check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_root_health_check(client):
    """GET / returns 200 with status ok."""
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# POST /items/lost
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_lost_item_happy_path(client, mock_service):
    """POST /items/lost returns 201 with item payload on success."""
    mock_service.register_item.return_value = _make_item_record(
        status=ItemStatus.LOST, item_id="lost-001"
    )
    png = _minimal_png()
    response = await client.post(
        "/items/lost",
        files={"image": ("test.png", png, "image/png")},
        data={"user_text": "red wallet"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "lost-001"
    assert body["status"] == "lost"
    mock_service.register_item.assert_called_once()


@pytest.mark.asyncio
async def test_register_lost_item_too_large(client, mock_service):
    """POST /items/lost returns 413 when image exceeds size limit."""
    mock_service.register_item.side_effect = ImageTooLargeError("too big")
    response = await client.post(
        "/items/lost",
        files={"image": ("big.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "image/png")},
        data={"user_text": ""},
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_register_lost_item_invalid_format(client, mock_service):
    """POST /items/lost returns 400 for unsupported image format."""
    mock_service.register_item.side_effect = InvalidImageError("bad format")
    response = await client.post(
        "/items/lost",
        files={"image": ("doc.txt", b"hello", "text/plain")},
        data={"user_text": ""},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_lost_item_corrupt(client, mock_service):
    """POST /items/lost returns 400 for corrupt image bytes."""
    mock_service.register_item.side_effect = CorruptImageError("corrupt")
    response = await client.post(
        "/items/lost",
        files={"image": ("bad.jpg", b"\xff\xd8\xff" + b"\x00" * 5, "image/jpeg")},
        data={"user_text": ""},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_lost_item_internal_error(client, mock_service):
    """POST /items/lost returns 500 on unexpected ItemManagerError."""
    mock_service.register_item.side_effect = ItemManagerError("db down")
    response = await client.post(
        "/items/lost",
        files={"image": ("test.png", _minimal_png(), "image/png")},
        data={"user_text": "wallet"},
    )
    assert response.status_code == 500


# ---------------------------------------------------------------------------
# POST /items/found
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_found_item_happy_path(client, mock_service):
    """POST /items/found returns 201 on success."""
    mock_service.register_item.return_value = _make_item_record(
        status=ItemStatus.FOUND, item_id="found-001"
    )
    response = await client.post(
        "/items/found",
        files={"image": ("found.png", _minimal_png(), "image/png")},
        data={"user_text": "blue backpack"},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "found"


@pytest.mark.asyncio
async def test_register_found_item_too_large(client, mock_service):
    """POST /items/found returns 413 when image is too large."""
    mock_service.register_item.side_effect = ImageTooLargeError("too big")
    response = await client.post(
        "/items/found",
        files={"image": ("big.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 10, "image/png")},
        data={"user_text": ""},
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_register_found_item_internal_error(client, mock_service):
    """POST /items/found returns 500 on unexpected error."""
    mock_service.register_item.side_effect = ItemManagerError("db down")
    response = await client.post(
        "/items/found",
        files={"image": ("test.png", _minimal_png(), "image/png")},
        data={"user_text": "bag"},
    )
    assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /items/{id}/matches
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_matches_happy_path(client, mock_service):
    """GET /items/{id}/matches returns 200 with match payload."""
    query_item = _make_item_response(status=ItemStatus.LOST, item_id="lost-001")
    candidate = _make_item_response(status=ItemStatus.FOUND, item_id="found-001")
    mock_service.find_matches.return_value = MatchQueryResponse(
        query_item=query_item,
        matches=[MatchItem(item=candidate, score=0.95, reason="same color")],
        total_candidates_evaluated=1,
    )
    response = await client.get("/items/lost-001/matches?k=3")
    assert response.status_code == 200
    body = response.json()
    assert body["query_item"]["id"] == "lost-001"
    assert len(body["matches"]) == 1
    assert body["matches"][0]["score"] == pytest.approx(0.95)


@pytest.mark.asyncio
async def test_get_matches_item_not_found(client, mock_service):
    """GET /items/{id}/matches returns 404 when item does not exist."""
    mock_service.find_matches.side_effect = ItemNotFoundError("not found")
    response = await client.get("/items/ghost-id/matches")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_matches_default_k(client, mock_service):
    """GET /items/{id}/matches uses k=3 by default."""
    query_item = _make_item_response(item_id="x")
    mock_service.find_matches.return_value = MatchQueryResponse(
        query_item=query_item, matches=[], total_candidates_evaluated=0
    )
    response = await client.get("/items/x/matches")
    assert response.status_code == 200
    mock_service.find_matches.assert_called_once_with(item_id="x", k=3)


@pytest.mark.asyncio
async def test_get_matches_server_error(client, mock_service):
    """GET /items/{id}/matches returns 500 on unexpected exception."""
    mock_service.find_matches.side_effect = RuntimeError("unexpected")
    response = await client.get("/items/some-id/matches")
    assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /items
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_items_all(client, mock_service):
    """GET /items returns all items when no status filter is given."""
    mock_service.list_items.return_value = [
        _make_item_record(status=ItemStatus.LOST, item_id="a"),
        _make_item_record(status=ItemStatus.FOUND, item_id="b"),
    ]
    response = await client.get("/items")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_list_items_filtered_by_status(client, mock_service):
    """GET /items?status=lost returns only lost items."""
    mock_service.list_items.return_value = [
        _make_item_record(status=ItemStatus.LOST, item_id="a"),
    ]
    response = await client.get("/items?status=lost")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["status"] == "lost"
    mock_service.list_items.assert_called_once_with(status=ItemStatus.LOST)


@pytest.mark.asyncio
async def test_list_items_empty(client, mock_service):
    """GET /items returns empty list when no items are registered."""
    mock_service.list_items.return_value = []
    response = await client.get("/items")
    assert response.status_code == 200
    assert response.json() == []
