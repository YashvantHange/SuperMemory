"""Bridge GitHub-compatible SuperMemory MCP API onto UALLService."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

from storage.adapters.file import get_storage
from uall.service import UALLService


class SuperMemoryBridge:
    def __init__(self, storage_root: str | None = None) -> None:
        self.storage_root = (
            storage_root
            or os.getenv("SUPERMEMORY_STORAGE_PATH")
            or os.getenv("UALL_DATA_DIR")
            or ".supermemory"
        )
        self._service: UALLService | None = None

    async def service(self) -> UALLService:
        if self._service is None:
            storage = get_storage(data_dir=self.storage_root)
            self._service = UALLService(storage)
            await self._service.init()
        return self._service

    async def reset(self) -> None:
        self._service = None
