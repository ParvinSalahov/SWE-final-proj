from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from ai.schemas import ItemDescription


class ItemStatus(str, Enum):
    """Status indicating whether an item is lost or found."""
    LOST = "lost"
    FOUND = "found"


class ItemBase(BaseModel):
    user_text: str = Field(..., description="User-supplied description of the item")


class ItemCreate(ItemBase):
    status: ItemStatus


class ItemRecord(BaseModel):
    """Complete domain and persistence model representing an item in storage."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: ItemStatus
    user_text: str
    image_path: str
    description: ItemDescription
    embedding: list[float] | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ItemResponse(BaseModel):
    """Response model returned by HTTP API and CLI for item queries."""
    id: str
    status: ItemStatus
    user_text: str
    image_path: str
    description: ItemDescription
    created_at: datetime


class MatchItem(BaseModel):
    """A matched candidate with its similarity score and reasoning."""
    item: ItemResponse
    score: float = Field(..., ge=-1.0, le=1.0, description="Cosine similarity score")
    reason: str = ""


class MatchQueryResponse(BaseModel):
    """Response model for GET /items/{id}/matches."""
    query_item: ItemResponse
    matches: list[MatchItem]
    total_candidates_evaluated: int
