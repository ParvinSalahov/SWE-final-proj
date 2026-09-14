"""Persistent storage repository interface and implementations.

# TODO (Task 3 - Storage):
# 1. Define BaseItemRepository (Abstract Base Class) with methods:
#    - save(item: ItemRecord) -> None
#    - get_by_id(item_id: str) -> ItemRecord | None
#    - list_all(status: ItemStatus | None = None) -> list[ItemRecord]
#    - list_by_status(status: ItemStatus) -> list[ItemRecord]
# 2. Implement PostgresItemRepository using asyncpg or psycopg2:
#    - Create table: items (id UUID/VARCHAR, status VARCHAR, user_text TEXT, image_path TEXT, description JSONB, embedding BYTEA/FLOAT[], created_at TIMESTAMP)
#    - Connect using settings.DATABASE_URL
# 3. Implement InMemoryItemRepository or SqliteItemRepository for offline testing.
"""
