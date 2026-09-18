"""AI service wrapper around the provided ai package.

Features:
- Tenacity retry logic with exponential backoff for transient errors
- In-memory session caching for text embeddings
- Structured logging with performance timings
- Bounded concurrency with asyncio.Semaphore and timeouts
"""

from __future__ import annotations

import asyncio
import hashlib
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
        max_concurrent_requests: int | None = None,
    ):
        self.cache_enabled = cache_enabled
        # In-memory session cache: normalized_hash -> np.ndarray
        self._embedding_cache: dict[str, np.ndarray] = {}
        
        limit = max_concurrent_requests or 5
        self._semaphore = asyncio.Semaphore(limit)

    def _normalize_key(self, text: str) -> str:
        """Create a stable hash key for normalized string."""
        return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()

    def describe_item(
        self,
        image_path: str,
        user_text: str = "",
        *,
        vlm: Any = None,
    ) -> ItemDescription:
        """Call VLM to describe an item, wrapped with exponential backoff and timings."""
        max_retries = getattr(settings, "AI_MAX_RETRIES", 3)
        min_wait = getattr(settings, "AI_RETRY_MIN_WAIT", 1.0)
        max_wait = getattr(settings, "AI_RETRY_MAX_WAIT", 8.0)

        @retry(
            reraise=True,
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(min=min_wait, max=max_wait),
            retry=retry_if_exception(is_transient_error),
        )
        def _call_vlm() -> ItemDescription:
            start_time = time.perf_counter()
            logger.info("Calling VLM for image: %s (user_text=%r)", image_path, user_text)
            res = ai.describe_item(image_path, user_text, vlm=vlm)
            elapsed = time.perf_counter() - start_time
            logger.info(
                "VLM completed in %.2fs. Object class=%r, confidence=%.2f",
                elapsed,
                res.object_class,
                res.confidence,
            )
            return res

        return _call_vlm()

    def get_embedding(
        self,
        text: str,
        *,
        embedder: Any = None,
    ) -> np.ndarray:
        """Fetch embedding vector with session cache and retries."""
        cache_key = self._normalize_key(text)

        if self.cache_enabled and cache_key in self._embedding_cache:
            logger.debug("Embedding cache HIT for text: '%.40s...'", text.strip())
            return self._embedding_cache[cache_key].copy()

        max_retries = getattr(settings, "AI_MAX_RETRIES", 3)
        min_wait = getattr(settings, "AI_RETRY_MIN_WAIT", 1.0)
        max_wait = getattr(settings, "AI_RETRY_MAX_WAIT", 8.0)

        @retry(
            reraise=True,
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(min=min_wait, max=max_wait),
            retry=retry_if_exception(is_transient_error),
        )
        def _call_embed() -> np.ndarray:
            start_time = time.perf_counter()
            logger.info("Embedding cache MISS. Generating embedding for text: '%.40s...'", text.strip())
            
            vec = ai.embed(text, embedder=embedder)
                
            elapsed = time.perf_counter() - start_time
            logger.info("Embedding completed in %.2fs (dim=%d)", elapsed, len(vec))
            return np.asarray(vec, dtype=np.float32)

        vec = _call_embed()
        if self.cache_enabled:
            self._embedding_cache[cache_key] = vec
        return vec.copy()

    async def describe_item_async(
        self,
        image_path: str,
        user_text: str = "",
        *,
        vlm: Any = None,
        timeout: float = 30.0,
    ) -> ItemDescription:
        """Async version respecting concurrency semaphore and timeout."""
        async with self._semaphore:
            return await asyncio.wait_for(
                asyncio.to_thread(self.describe_item, image_path, user_text, vlm=vlm),
                timeout=timeout,
            )

    async def get_embedding_async(
        self,
        text: str,
        *,
        embedder: Any = None,
        timeout: float = 15.0,
    ) -> np.ndarray:
        """Async version respecting concurrency semaphore and timeout."""
        async with self._semaphore:
            return await asyncio.wait_for(
                asyncio.to_thread(self.get_embedding, text, embedder=embedder),
                timeout=timeout,
            )

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._embedding_cache.clear()
        logger.info("AI embedding cache cleared")