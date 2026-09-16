"""Concurrency pipeline for batch item processing and matching."""

import asyncio
import time
from typing import Any

from src.core.item_manager import ItemManager
from src.models import ItemRecord


async def batch_register_items(
    items: list[dict[str, Any]],
    item_manager: ItemManager,
    max_concurrency: int = 5,
) -> list[ItemRecord]:
    """Register multiple items concurrently with bounded parallelism."""

    if max_concurrency < 1:
        raise ValueError("max_concurrency must be at least 1")

    semaphore = asyncio.Semaphore(max_concurrency)

    async def register_one(item: dict[str, Any]) -> ItemRecord:
        async with semaphore:
            return await item_manager.register_item(
                status=item["status"],
                image_bytes=item["image_bytes"],
                filename=item["filename"],
                user_text=item["user_text"],
                vlm=item.get("vlm"),
                embedder=item.get("embedder"),
            )

    tasks = [register_one(item) for item in items]

    return await asyncio.gather(*tasks)


async def sequential_register_items(
    items: list[dict[str, Any]],
    item_manager: ItemManager,
) -> list[ItemRecord]:
    """Register items sequentially for benchmark comparison."""

    results: list[ItemRecord] = []

    for item in items:
        result = await item_manager.register_item(
            status=item["status"],
            image_bytes=item["image_bytes"],
            filename=item["filename"],
            user_text=item["user_text"],
            vlm=item.get("vlm"),
            embedder=item.get("embedder"),
        )
        results.append(result)

    return results


async def sequential_vs_concurrent_benchmark(
    items: list[dict[str, Any]],
    item_manager: ItemManager,
    max_concurrency: int = 5,
) -> dict[str, float]:
    """Measure sequential and concurrent batch registration time."""

    start = time.perf_counter()
    await sequential_register_items(items, item_manager)
    sequential_time = time.perf_counter() - start

    start = time.perf_counter()
    await batch_register_items(
        items,
        item_manager,
        max_concurrency=max_concurrency,
    )
    concurrent_time = time.perf_counter() - start

    return {
        "sequential_seconds": sequential_time,
        "concurrent_seconds": concurrent_time,
        "speedup": (
            sequential_time / concurrent_time
            if concurrent_time > 0
            else 0.0
        ),
    }