"""FastAPI application for Lost & Found Service.

Endpoints:
1. POST /items/lost          - Register a lost item (multipart image + user_text)
2. POST /items/found         - Register a found item (multipart image + user_text)
3. GET  /items/{id}/matches  - Get top-k matches from the opposite pool
4. GET  /items               - List items optionally filtered by status (lost/found)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import logging
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Path, Query, UploadFile, status

from src.storage.database import create_tables
from src.config import configure_logging, ensure_ai_provider_env
from src.models import ItemResponse, ItemStatus, MatchQueryResponse
from src.core.item_manager import (
    CorruptImageError,
    ImageTooLargeError,
    InvalidImageError,
    ItemNotFoundError,
    ItemRecord,
    ItemManager,
    ItemManagerError,
)

# Initialize logging and core services
configure_logging()
ensure_ai_provider_env()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(
    title="Smart Lost & Found API",
    description="Vision-language AI service to register and match lost and found items.",
    lifespan=lifespan,
)

# Shared service instance
service = ItemManager()


def _to_response(item: ItemRecord) -> ItemResponse:
    """Helper to convert an ItemRecord to an ItemResponse."""
    return ItemResponse(
        id=item.id,
        status=item.status,
        user_text=item.user_text,
        image_path=item.image_path,
        description=item.description,
        created_at=item.created_at,
    )


@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "message": "Smart Lost & Found API is running"}


@app.post(
    "/items/lost",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Items"],
    summary="Register a lost item",
)
async def register_lost_item(
    image: Annotated[
        UploadFile, File(description="Image of the lost item (JPEG or PNG, <= 5MB)")
    ],
    user_text: Annotated[
        str, Form(description="User description and context of the lost item")
    ] = "",
) -> ItemResponse:
    """Upload an image and description of a lost item."""
    try:
        image_bytes = await image.read()
        item = await service.register_item(
            status=ItemStatus.LOST,
            image_bytes=image_bytes,
            filename=image.filename or "lost.jpg",
            user_text=user_text,
        )
        return _to_response(item)
    except ImageTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    except (InvalidImageError, CorruptImageError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except ItemManagerError as exc:
        logger.exception("Failed to register lost item: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


@app.post(
    "/items/found",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Items"],
    summary="Register a found item",
)
async def register_found_item(
    image: Annotated[
        UploadFile, File(description="Image of the found item (JPEG or PNG, <= 5MB)")
    ],
    user_text: Annotated[
        str, Form(description="User description and context of the found item")
    ] = "",
) -> ItemResponse:
    """Upload an image and description of a found item."""
    try:
        image_bytes = await image.read()
        item = await service.register_item(
            status=ItemStatus.FOUND,
            image_bytes=image_bytes,
            filename=image.filename or "found.jpg",
            user_text=user_text,
        )
        return _to_response(item)
    except ImageTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    except (InvalidImageError, CorruptImageError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except ItemManagerError as exc:
        logger.exception("Failed to register found item: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


@app.get(
    "/items/{id}/matches",
    response_model=MatchQueryResponse,
    tags=["Matches"],
    summary="Find matches for an item",
)
async def get_item_matches(
    id: Annotated[str, Path(description="The ID of the item to match against")],
    k: Annotated[
        int, Query(ge=1, le=50, description="Maximum number of top matches to return")
    ] = 3,
) -> MatchQueryResponse:
    """Find the top-k most likely matches from the opposite pool."""
    try:
        return await service.find_matches(item_id=id, k=k)
    except ItemNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.exception("Error matching item %s: %s", id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


@app.get(
    "/items",
    response_model=list[ItemResponse],
    tags=["Items"],
    summary="List items",
)
async def list_items(
    status: Annotated[
        ItemStatus | None, Query(description="Filter by item status (lost or found)")
    ] = None,
) -> list[ItemResponse]:
    """List all registered items, optionally filtered by status (lost/found)."""
    items = await service.list_items(status=status)
    return [_to_response(item) for item in items]
