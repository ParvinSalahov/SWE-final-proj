import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from ai.schemas import ItemDescription
from src.models import ItemRecord
from src.storage.database import ItemDB
from src.models import ItemStatus
from src.storage.repository import PostgresItemRepository


def test_embedding_to_bytes_and_back():
    embedding = [0.1, 0.2, 0.3]

    data = PostgresItemRepository._embedding_to_bytes(embedding)

    assert isinstance(data, bytes)

    restored = PostgresItemRepository._embedding_from_bytes(data)

    assert restored is not None
    assert len(restored) == 3

    for original, actual in zip(embedding, restored):
        assert actual == pytest.approx(original)


def test_embedding_none_conversion():
    assert PostgresItemRepository._embedding_to_bytes(None) is None
    assert PostgresItemRepository._embedding_from_bytes(None) is None

from datetime import datetime, timezone
from unittest.mock import AsyncMock

from ai.schemas import ItemDescription
from src.models import ItemRecord
from src.storage.database import ItemDB


class FakeResult:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    def scalar_one_or_none(self):
        return self.row

    def scalars(self):
        return self

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, result=None):
        self.result = result
        self.added = None
        self.commit = AsyncMock()
        self.execute = AsyncMock(return_value=result)

    def add(self, row):
        self.added = row

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

def make_item() -> ItemRecord:
    return ItemRecord(
        id="test-item-1",
        status=ItemStatus.LOST,
        user_text="Black umbrella",
        image_path="storage/images/test.png",
        description=ItemDescription(
            object_class="umbrella",
            colors=["black"],
            confidence=0.95,
            brand="Fulton",
            distinguishing_marks=["bent rib"],
            location_hints=["library"],
        ),
        embedding=[0.1, 0.2, 0.3],
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_save(monkeypatch):
    item = make_item()
    session = FakeSession()

    class FakeSessionLocal:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(
        "src.storage.repository.SessionLocal",
        lambda: FakeSessionLocal(),
    )

    repository = PostgresItemRepository()

    await repository.save(item)

    assert isinstance(session.added, ItemDB)
    assert session.added.id == item.id
    assert session.added.status == "lost"
    assert session.added.user_text == "Black umbrella"
    assert session.added.embedding is not None

    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_id(monkeypatch):
    item = make_item()

    row = ItemDB(
        id=item.id,
        status=item.status.value,
        user_text=item.user_text,
        image_path=item.image_path,
        description=item.description.model_dump(),
        embedding=PostgresItemRepository._embedding_to_bytes(
            item.embedding
        ),
        created_at=item.created_at,
    )

    session = FakeSession(FakeResult(row=row))

    class FakeSessionLocal:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(
        "src.storage.repository.SessionLocal",
        lambda: FakeSessionLocal(),
    )

    repository = PostgresItemRepository()

    result = await repository.get_by_id(item.id)

    assert result is not None
    assert result.id == item.id
    assert result.status == ItemStatus.LOST
    assert result.user_text == "Black umbrella"
    assert result.embedding == pytest.approx(item.embedding)


@pytest.mark.asyncio
async def test_get_by_id_returns_none(monkeypatch):
    session = FakeSession(FakeResult(row=None))

    class FakeSessionLocal:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(
        "src.storage.repository.SessionLocal",
        lambda: FakeSessionLocal(),
    )

    repository = PostgresItemRepository()

    result = await repository.get_by_id("does-not-exist")

    assert result is None


@pytest.mark.asyncio
async def test_list_all(monkeypatch):
    lost_item = make_item()

    found_item = ItemDB(
        id="test-item-2",
        status="found",
        user_text="Blue backpack",
        image_path="storage/images/backpack.png",
        description={
            "object_class": "backpack",
            "colors": ["blue"],
            "confidence": 0.9,
        },
        embedding=None,
        created_at=datetime.now(timezone.utc),
    )

    lost_row = ItemDB(
        id=lost_item.id,
        status=lost_item.status.value,
        user_text=lost_item.user_text,
        image_path=lost_item.image_path,
        description=lost_item.description.model_dump(),
        embedding=PostgresItemRepository._embedding_to_bytes(
            lost_item.embedding
        ),
        created_at=lost_item.created_at,
    )

    session = FakeSession(
        FakeResult(rows=[lost_row, found_item])
    )

    class FakeSessionLocal:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(
        "src.storage.repository.SessionLocal",
        lambda: FakeSessionLocal(),
    )

    repository = PostgresItemRepository()

    result = await repository.list_all()

    assert len(result) == 2
    assert result[0].id == "test-item-1"
    assert result[1].id == "test-item-2"


@pytest.mark.asyncio
async def test_list_all_filtered_by_status(monkeypatch):
    item = make_item()

    row = ItemDB(
        id=item.id,
        status="lost",
        user_text=item.user_text,
        image_path=item.image_path,
        description=item.description.model_dump(),
        embedding=PostgresItemRepository._embedding_to_bytes(
            item.embedding
        ),
        created_at=item.created_at,
    )

    session = FakeSession(FakeResult(rows=[row]))

    class FakeSessionLocal:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(
        "src.storage.repository.SessionLocal",
        lambda: FakeSessionLocal(),
    )

    repository = PostgresItemRepository()

    result = await repository.list_all(status=ItemStatus.LOST)

    assert len(result) == 1
    assert result[0].id == item.id
    assert result[0].status == ItemStatus.LOST
