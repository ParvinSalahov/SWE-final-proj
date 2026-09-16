"""Shared pytest fixtures for the AI smoke tests.

The fakes live here so both the AI smoke tests and any student-written
tests can reuse them without monkey-patching modules.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pytest

from ai.providers.base import VLMProvider, EmbeddingProvider
from PIL import Image


class FakeVLM(VLMProvider):
    """Returns a fixed JSON response. No network."""

    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.payload = payload or {
            "object_class": "umbrella",
            "colors": ["black"],
            "brand": "Fulton",
            "distinguishing_marks": ["bent rib"],
            "location_hints": ["library entrance"],
            "confidence": 0.85,
        }
        self.calls: list[tuple[str, str]] = []

    def describe(
        self,
        image_path: str,
        prompt: str,
        *,
        json_schema: dict | None = None,
    ) -> str:
        self.calls.append((image_path, prompt))
        return json.dumps(self.payload)


class FakeEmbedder(EmbeddingProvider):
    """Deterministic toy embedder: 8-D unit vectors derived from a hash.

    Same input -> same output, different input -> different (but stable) output.
    Used by tests so we don't need network access.
    """

    def __init__(self, dim: int = 8) -> None:
        self._dim = dim
        self.calls = 0

    @property
    def dimension(self) -> int:
        return self._dim

    def embed(self, text: str) -> np.ndarray:
        self.calls += 1

        if not text.strip():
            raise ValueError("Cannot embed empty string.")
        rng = np.random.default_rng(seed=abs(hash(text)) % (2**31))
        v = rng.standard_normal(self._dim).astype(np.float32)
        v /= np.linalg.norm(v)
        return v


@pytest.fixture
def fake_vlm() -> FakeVLM:
    return FakeVLM()


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def sample_image(tmp_path):
    """Create a tiny valid PNG image for tests."""
    p = tmp_path / "tiny.png"

    image = Image.new("RGB", (1, 1), color="black")
    image.save(p, format="PNG")

    return str(p)
