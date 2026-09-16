from pathlib import Path

import pytest
import numpy as np
from src.core.item_manager import ItemManager
from src.models import ItemStatus
from src.storage.image_storage import ImageStorage
from src.storage.repository import BaseItemRepository


class FakeRepository(BaseItemRepository):
    def __init__(self) -> None:
        self.items = {}

    async def save(self, item):
        self.items[item.id] = item

    async def get_by_id(self, item_id):
        return self.items.get(item_id)

    async def list_all(self, status=None):
        if status is None:
            return list(self.items.values())

        return [
            item
            for item in self.items.values()
            if item.status == status
        ]


@pytest.mark.asyncio
async def test_register_item_happy_path(
    sample_image,
    fake_vlm,
    fake_embedder,
    tmp_path,
):
    image_bytes = Path(sample_image).read_bytes()

    manager = ItemManager(
        storage_dir=tmp_path / "images",
        repository=FakeRepository(),
    )

    item = await manager.register_item(
        status=ItemStatus.LOST,
        image_bytes=image_bytes,
        filename="umbrella.png",
        user_text="Black umbrella",
        vlm=fake_vlm,
        embedder=fake_embedder,
    )

    assert item.status == ItemStatus.LOST
    assert item.user_text == "Black umbrella"
    assert item.description.object_class == "umbrella"
    assert item.embedding is not None
    assert len(item.embedding) == 8
    assert Path(item.image_path).exists()

from src.core.item_manager import CorruptImageError

@pytest.mark.asyncio
async def test_register_item_rejects_corrupted_image(
    fake_vlm,
    fake_embedder,
    tmp_path,
):
    corrupted_image = b"\x89PNG\r\n\x1a\nthis-is-not-a-real-png"

    manager = ItemManager(
        storage_dir=tmp_path / "images",
        repository=FakeRepository(),
    )

    with pytest.raises(CorruptImageError):
        await manager.register_item(
            status=ItemStatus.LOST,
            image_bytes=corrupted_image,
            filename="broken.png",
            user_text="Broken image",
            vlm=fake_vlm,
            embedder=fake_embedder,
        )

    image_dir = tmp_path / "images"

    if image_dir.exists():
        assert list(image_dir.iterdir()) == []

@pytest.mark.asyncio
async def test_register_item_cleans_up_image_when_vlm_fails(
    fake_embedder,
    tmp_path,
):
    class FailingVLM:
        def describe(self, *args, **kwargs):
            raise RuntimeError("VLM service failed")

    manager = ItemManager(
        storage_dir=tmp_path / "images",
        repository=FakeRepository(),
    )

    valid_image = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108020000"
        "00907753de0000000c4944415408d76360000000000004000146a13a"
        "020000000049454e44ae426082"
    )

    with pytest.raises(Exception):
        await manager.register_item(
            status=ItemStatus.LOST,
            image_bytes=valid_image,
            filename="test.png",
            user_text="Test image",
            vlm=FailingVLM(),
            embedder=fake_embedder,
        )

    image_dir = tmp_path / "images"

    if image_dir.exists():
        assert list(image_dir.iterdir()) == []

@pytest.mark.asyncio
async def test_register_item_cleans_up_image_when_embedding_fails(
    fake_vlm,
    tmp_path,
):
    class FailingEmbedder:
        def __init__(self, dim: int = 8):
            self._dim = dim
            self.calls = 0

        @property
        def dimension(self):
            return 8

        def embed(self, text: str) -> np.ndarray:
            self.calls += 1

            if not text.strip():
                raise ValueError("Cannot embed empty string.")

            rng = np.random.default_rng(seed=abs(hash(text)) % (2 ** 31))
            v = rng.standard_normal(self._dim).astype(np.float32)
            v /= np.linalg.norm(v)
            return v

    manager = ItemManager(
        storage_dir=tmp_path / "images",
        repository=FakeRepository(),
    )

    valid_image = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108020000"
        "00907753de0000000c4944415408d76360000000000004000146a13a"
        "020000000049454e44ae426082"
    )

    with pytest.raises(Exception):
        await manager.register_item(
            status=ItemStatus.LOST,
            image_bytes=valid_image,
            filename="test.png",
            user_text="Test image",
            vlm=fake_vlm,
            embedder=FailingEmbedder(),
        )

    image_dir = tmp_path / "images"

    if image_dir.exists():
        assert list(image_dir.iterdir()) == []

@pytest.mark.asyncio
async def test_find_matches_returns_top_match(
    sample_image,
    fake_vlm,
    fake_embedder,
    tmp_path,
):
    manager = ItemManager(
        storage_dir=tmp_path / "images",
        repository=FakeRepository(),
    )

    image_bytes = Path(sample_image).read_bytes()

    lost_item = await manager.register_item(
        status=ItemStatus.LOST,
        image_bytes=image_bytes,
        filename="lost.png",
        user_text="Black umbrella",
        vlm=fake_vlm,
        embedder=fake_embedder,
    )

    found_item = await manager.register_item(
        status=ItemStatus.FOUND,
        image_bytes=image_bytes,
        filename="found.png",
        user_text="Black umbrella",
        vlm=fake_vlm,
        embedder=fake_embedder,
    )

    result = await manager.find_matches(lost_item.id, k=1)

    assert result.query_item.id == lost_item.id
    assert len(result.matches) == 1
    assert result.matches[0].item.id == found_item.id
    assert result.total_candidates_evaluated == 1
    assert result.matches[0].score > 0

@pytest.mark.asyncio
async def test_embedding_cache_reuses_same_description(
    sample_image,
    fake_vlm,
    fake_embedder,
    tmp_path,
):
    manager = ItemManager(
        storage_dir=tmp_path / "images",
        repository=FakeRepository(),
    )

    image_bytes = Path(sample_image).read_bytes()

    await manager.register_item(
        status=ItemStatus.LOST,
        image_bytes=image_bytes,
        filename="first.png",
        user_text="Black umbrella",
        vlm=fake_vlm,
        embedder=fake_embedder,
    )

    await manager.register_item(
        status=ItemStatus.FOUND,
        image_bytes=image_bytes,
        filename="second.png",
        user_text="Black umbrella",
        vlm=fake_vlm,
        embedder=fake_embedder,
    )

    assert fake_embedder.calls == 1