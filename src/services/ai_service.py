"""AI service wrapper around the provided ai package.

Features:
- Tenacity retry logic with exponential backoff for transient errors
- In-memory session caching for text embeddings
- Structured logging with performance timings
- Bounded concurrency with asyncio.Semaphore

# TODO (Optional Bonus): Multi-provider failover (switch to secondary if primary fails)
# TODO (Optional Bonus): Cost telemetry (record tokens and $-estimate per call)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import numpy as np
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

import ai
from ai.schemas import ItemDescription
from src.config import settings

logger = logging.getLogger(__name__)


def is_transient_error(exc: BaseException) -> bool:
    """Determine whether an error is transient and safe to retry."""
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True
    msg = str(exc).lower()
    return any(
        marker in msg
        for marker in [
            "429",
            "rate limit",
            "500",
            "502",
            "503",
            "504",
            "timeout",
            "timed out",
        ]
    )


class AIService:
    """Wrapper around the provided ai package."""

    def __init__(
        self,
        cache_enabled: bool = True,
        max_concurrent_requests: int = 5,
    ):
        self.cache_enabled = cache_enabled
        self._embedding_cache: dict[
            str, np.ndarray
        ] = {}  # Cache for search_text -> np.ndarray
        self._semaphore = asyncio.Semaphore(
            max_concurrent_requests
        )  # Concurrency bound to avoid hitting provider rate limits

    def describe_item(
        self,
        image_path: str,
        user_text: str = "",
        *,
        vlm: Any = None,
    ) -> ItemDescription:
        """Call VLM to describe an item, wrapped with exponential backoff and timings."""

        @retry(
            reraise=True,
            stop=stop_after_attempt(settings.AI_MAX_RETRIES),
            wait=wait_exponential(
                min=settings.AI_RETRY_MIN_WAIT,
                max=settings.AI_RETRY_MAX_WAIT,
            ),
            retry=retry_if_exception(is_transient_error),
        )
        def _call_vlm() -> ItemDescription:
            start_time = time.perf_counter()
            logger.info(
                "Calling VLM for image: %s (user_text=%r)", image_path, user_text
            )
            res = ai.describe_item(image_path, user_text, vlm=vlm)
            elapsed = time.perf_counter() - start_time
            logger.info(
                "VLM completed in %.2fs. Object class=%r, confidence=%.2f",
                elapsed,
                res.object_class,
                res.confidence,
            )
            logger.debug("VLM full description: %s", res.model_dump_json())
            return res

        return _call_vlm()

    def get_embedding(
        self,
        text: str,
        *,
        embedder: Any = None,
    ) -> np.ndarray:
        """Fetch embedding vector with session cache and retries."""
        cache_key = text.strip()

        if self.cache_enabled and cache_key in self._embedding_cache:
            logger.debug("Embedding cache HIT for: %r", cache_key[:50])
            return self._embedding_cache[cache_key]

        @retry(
            reraise=True,
            stop=stop_after_attempt(settings.AI_MAX_RETRIES),
            wait=wait_exponential(
                min=settings.AI_RETRY_MIN_WAIT,
                max=settings.AI_RETRY_MAX_WAIT,
            ),
            retry=retry_if_exception(is_transient_error),
        )
        def _call_embed() -> np.ndarray:
            start_time = time.perf_counter()
            logger.info(
                "Generating embedding for text: %r (len=%d)", cache_key[:60], len(text)
            )
            vec = ai.embed(text, embedder=embedder)
            elapsed = time.perf_counter() - start_time
            logger.info("Embedding completed in %.2fs (dim=%d)", elapsed, len(vec))
            return vec

        vec = _call_embed()
        if self.cache_enabled:
            self._embedding_cache[cache_key] = vec
        return vec

    async def describe_item_async(
        self,
        image_path: str,
        user_text: str = "",
        *,
        vlm: Any = None,
    ) -> ItemDescription:
        """Async version respecting concurrency semaphore."""
        async with self._semaphore:
            return await asyncio.to_thread(
                self.describe_item, image_path, user_text, vlm=vlm
            )

    async def get_embedding_async(
        self,
        text: str,
        *,
        embedder: Any = None,
    ) -> np.ndarray:
        """Async version respecting concurrency semaphore."""
        async with self._semaphore:
            return await asyncio.to_thread(self.get_embedding, text, embedder=embedder)

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._embedding_cache.clear()
