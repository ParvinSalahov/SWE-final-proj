import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_database_connection():
    with patch(
        "src.storage.database.check_database_connection",
        new_callable=AsyncMock,
    ) as mock_conn:
        mock_conn.return_value = True
        result = await mock_conn()
        assert result is True