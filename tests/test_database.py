import pytest

from src.storage.database import check_database_connection


@pytest.mark.asyncio
async def test_database_connection():
    result = await check_database_connection()

    assert result is True
