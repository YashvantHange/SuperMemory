"""Tier 3: PostgreSQL enterprise adapter — delegates to file storage with postgres hooks."""

import os

from storage.adapters.file import FileStorageAdapter


class PostgresStorageAdapter(FileStorageAdapter):
    """
    Enterprise tier stub: uses file storage locally with postgres connection config.
    Full postgres/qdrant/redis integration requires optional deps and running services.
    """

    def __init__(self, base_dir: str | None = None):
        data_dir = base_dir or os.environ.get("UALL_DATA_DIR", ".uall")
        super().__init__(data_dir)
        self.postgres_url = os.environ.get(
            "UALL_POSTGRES_URL", "postgresql://uall:uall@localhost:5432/uall"
        )
        self.qdrant_url = os.environ.get("UALL_QDRANT_URL", "http://localhost:6333")
        self.redis_url = os.environ.get("UALL_REDIS_URL", "redis://localhost:6379")

    async def init(self) -> None:
        await super().init()
        # Enterprise hooks: connect to external services when available
        self._enterprise_ready = False
        try:
            import asyncpg  # noqa: F401

            self._enterprise_ready = True
        except ImportError:
            pass
