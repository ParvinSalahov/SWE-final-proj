from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
import struct

from sqlalchemy import select

from src.models import ItemRecord, ItemStatus
from src.storage.database import ItemDB, SessionLocal


class BaseItemRepository(ABC):
    """Abstract interface for persistent item storage."""

    @abstractmethod
    async def save(self, item: ItemRecord) -> None:
        """Save an item."""

    @abstractmethod
    async def get_by_id(self, item_id: str) -> ItemRecord | None:
        """Get an item by its ID."""

    @abstractmethod
    async def list_all(
        self,
        status: ItemStatus | None = None,
    ) -> list[ItemRecord]:
        """List all items, optionally filtered by status."""

    async def list_by_status(
        self,
        status: ItemStatus,
    ) -> list[ItemRecord]:
        """List items having the given status."""
        return await self.list_all(status=status)


class PostgresItemRepository(BaseItemRepository):
    """PostgreSQL implementation of the item repository."""

    @staticmethod
    def _embedding_to_bytes(
        embedding: list[float] | None,
    ) -> bytes | None:
        """Convert a list of floats to binary representation."""
        if embedding is None:
            return None

        return struct.pack(f"{len(embedding)}f", *embedding)

    @staticmethod
    def _embedding_from_bytes(
        data: bytes | None,
    ) -> list[float] | None:
        """Convert binary embedding back to a list of floats."""
        if data is None:
            return None

        count = len(data) // 4
        return list(struct.unpack(f"{count}f", data))

    @staticmethod
    def _to_record(row: ItemDB) -> ItemRecord:
        """Convert a database row into a domain model."""
        return ItemRecord(
            id=row.id,
            status=ItemStatus(row.status),
            user_text=row.user_text,
            image_path=row.image_path,
            description=row.description,
            embedding=PostgresItemRepository._embedding_from_bytes(
                row.embedding
            ),
            created_at=row.created_at,
        )

    async def save(self, item: ItemRecord) -> None:
        """Save an item to PostgreSQL."""
        async with SessionLocal() as session:
            row = ItemDB(
                id=item.id,
                status=item.status.value,
                user_text=item.user_text,
                image_path=item.image_path,
                description=item.description.model_dump(),
                embedding=self._embedding_to_bytes(item.embedding),
                created_at=item.created_at,
            )

            session.add(row)
            await session.commit()

    async def get_by_id(self, item_id: str) -> ItemRecord | None:
        """Get an item by its ID."""
        async with SessionLocal() as session:
            result = await session.execute(
                select(ItemDB).where(ItemDB.id == item_id)
            )

            row = result.scalar_one_or_none()

            if row is None:
                return None

            return self._to_record(row)

    async def list_all(
        self,
        status: ItemStatus | None = None,
    ) -> list[ItemRecord]:
        """List all items, optionally filtered by status."""
        async with SessionLocal() as session:
            statement = select(ItemDB)

            if status is not None:
                statement = statement.where(
                    ItemDB.status == status.value
                )

            statement = statement.order_by(ItemDB.created_at)

            result = await session.execute(statement)
            rows = result.scalars().all()

            return [self._to_record(row) for row in rows]