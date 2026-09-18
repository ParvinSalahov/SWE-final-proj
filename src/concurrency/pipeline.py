"""Concurrency pipeline for batch item processing and matching."""

from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Protocol

from src.models import ItemRecord


class ItemManagerLike(Protocol):
    """Minimal manager interface required by the concurrency pipeline."""

    def register_item(
        self,
        status: Any,
        image_bytes: bytes,
        filename: str,
        user_text: str,
        *,
        vlm: Any = None,
        embedder: Any = None,
    ) -> Any:
        """Register one item, synchronously or asynchronously."""


async def _invoke_register(item_manager: Any, **kwargs) -> ItemRecord:
    """Helper to call register_item whether it is async or synchronous."""
    res = item_manager.register_item(**kwargs)
    if inspect.isawaitable(res):
        return await res
    return await asyncio.to_thread(lambda: res)


async def batch_register_items(
    items: list[Any],
    item_manager: ItemManagerLike,
    max_concurrency: int = 5,
) -> list[ItemRecord]:
    """Register multiple items concurrently with bounded parallelism."""
    if max_concurrency < 1:
        raise ValueError("max_concurrency must be at least 1")

    semaphore = asyncio.Semaphore(max_concurrency)

    async def register_one(item: Any) -> ItemRecord:
        async with semaphore:
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

            return await _invoke_register(
                item_manager,
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
    item_manager: ItemManagerLike,
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

        result = await _invoke_register(
            item_manager,
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
    item_manager: ItemManagerLike,
    max_concurrency: int = 5,
) -> dict[str, float]:
    """Measure sequential and concurrent batch registration time."""
    ai_service = getattr(item_manager, "ai_service", None)
    if ai_service and hasattr(ai_service, "clear_cache"):
        ai_service.clear_cache()

    start = time.perf_counter()
    await sequential_register_items(items, item_manager)
    sequential_time = time.perf_counter() - start

    if ai_service and hasattr(ai_service, "clear_cache"):
        ai_service.clear_cache()

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