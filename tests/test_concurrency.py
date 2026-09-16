import asyncio

import pytest

from ai.schemas import ItemDescription
from src.concurrency.pipeline import batch_register_items
from src.models import ItemRecord, ItemStatus


class FakeItemManager:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def register_item(
        self,
        status: ItemStatus,
        image_bytes: bytes,
        filename: str,
        user_text: str,
        *,
        vlm=None,
        embedder=None,
    ) -> ItemRecord:
        self.active += 1
        self.max_active = max(self.max_active, self.active)

        await asyncio.sleep(0.05)

        self.active -= 1

        description = ItemDescription(
            object_class="test object",
            colors=["black"],
            confidence=1.0,
            brand=None,
            distinguishing_marks=[],
            location_hints=[],
        )

        return ItemRecord(
            id=user_text,
            status=status,
            user_text=user_text,
            image_path=filename,
            description=description,
            embedding=None,
        )


@pytest.mark.asyncio
async def test_batch_register_respects_concurrency_limit():
    manager = FakeItemManager()

    items = [
        {
            "status": ItemStatus.LOST,
            "image_bytes": b"fake-image",
            "filename": f"image-{i}.png",
            "user_text": f"item-{i}",
        }
        for i in range(10)
    ]

    results = await batch_register_items(
        items,
        manager,
        max_concurrency=3,
    )

    assert len(results) == 10
    assert manager.max_active <= 3
    assert manager.max_active == 3

@pytest.mark.asyncio
async def test_sequential_vs_concurrent_benchmark():
    from src.concurrency.pipeline import sequential_vs_concurrent_benchmark

    manager = FakeItemManager()

    items = [
        {
            "status": ItemStatus.LOST,
            "image_bytes": b"fake-image",
            "filename": f"image-{i}.png",
            "user_text": f"item-{i}",
        }
        for i in range(10)
    ]

    result = await sequential_vs_concurrent_benchmark(
        items,
        manager,
        max_concurrency=5,
    )

    assert result["sequential_seconds"] > 0
    assert result["concurrent_seconds"] > 0
    assert result["speedup"] > 1