"""Concurrency pipeline for batch item processing and matching."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from src.core.item_manager import ItemManager
from src.models import ItemRecord


async def batch_register_items(
    items: list[Any],
    item_manager: ItemManager,
    max_concurrency: int = 5,
) -> list[ItemRecord]:
    """Register multiple items concurrently with bounded parallelism."""
    if max_concurrency < 1:
        raise ValueError("max_concurrency must be at least 1")

    semaphore = asyncio.Semaphore(max_concurrency)

    async def register_one(item: Any) -> ItemRecord:
        async with semaphore:
            # Model və ya dict girişini eyni dərəcədə təhlükəsiz qarşılamaq
            status = getattr(item, "status", None) or item["status"]
            image_bytes = getattr(item, "image_bytes", None) or item["image_bytes"]
            filename = getattr(item, "filename", None) or item["filename"]
            user_text = getattr(item, "user_text", None) or item["user_text"]
            vlm = getattr(item, "vlm", None) if hasattr(item, "vlm") else item.get("vlm")
            embedder = (
                getattr(item, "embedder", None)
                if hasattr(item, "embedder")
                else item.get("embedder")
            )

            # Bloklayan sinxron metodu async mühitdə thread-də icra edirik
            return await asyncio.to_thread(
                item_manager.register_item,
                status=status,
                image_bytes=image_bytes,
                filename=filename,
                user_text=user_text,
                vlm=vlm,
                embedder=embedder,
            )

    tasks = [register_one(item) for item in items]
    return await asyncio.gather(*tasks)


async def sequential_register_items(
    items: list[Any],
    item_manager: ItemManager,
) -> list[ItemRecord]:
    """Register items sequentially for benchmark comparison."""
    results: list[ItemRecord] = []

    for item in items:
        status = getattr(item, "status", None) or item["status"]
        image_bytes = getattr(item, "image_bytes", None) or item["image_bytes"]
        filename = getattr(item, "filename", None) or item["filename"]
        user_text = getattr(item, "user_text", None) or item["user_text"]
        vlm = getattr(item, "vlm", None) if hasattr(item, "vlm") else item.get("vlm")
        embedder = (
            getattr(item, "embedder", None)
            if hasattr(item, "embedder")
            else item.get("embedder")
        )

        result = await asyncio.to_thread(
            item_manager.register_item,
            status=status,
            image_bytes=image_bytes,
            filename=filename,
            user_text=user_text,
            vlm=vlm,
            embedder=embedder,
        )
        results.append(result)

    return results


async def sequential_vs_concurrent_benchmark(
    items: list[Any],
    item_manager: ItemManager,
    max_concurrency: int = 5,
) -> dict[str, float]:
    """Measure sequential and concurrent batch registration time with fair cache invalidation."""
    # 1. Ardıcıl ölçmə
    if hasattr(item_manager.ai_service, "clear_cache"):
        item_manager.ai_service.clear_cache()

    start = time.perf_counter()
    await sequential_register_items(items, item_manager)
    sequential_time = time.perf_counter() - start

    # 2. Ədalətli müqayisə üçün keşi yenidən təmizləyirik
    if hasattr(item_manager.ai_service, "clear_cache"):
        item_manager.ai_service.clear_cache()

    start = time.perf_counter()
    await batch_register_items(
        items,
        item_manager,
        max_concurrency=max_concurrency,
    )
    concurrent_time = time.perf_counter() - start

    speedup = (
        sequential_time / concurrent_time
        if concurrent_time > 0
        else 0.0
    )

    return {
        "sequential_seconds": sequential_time,
        "concurrent_seconds": concurrent_time,
        "speedup": speedup,
    }