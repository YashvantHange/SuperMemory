from datetime import datetime

from uall_core.ports.storage import StoragePort
from uall_core.schemas.common import VersionRecord


class RollbackManager:
    def __init__(self, storage: StoragePort):
        self.storage = storage

    async def save_version(
        self, resource_type: str, resource_id: str, version: str, content: dict, promoted: bool = False
    ) -> str:
        record = VersionRecord(
            resource_type=resource_type,
            resource_id=resource_id,
            version=version,
            content=content,
            promoted=promoted,
        )
        return await self.storage.save_version(record)

    async def rollback(self, resource_type: str, resource_id: str, target_version: str) -> dict:
        versions = await self.storage.list_versions(resource_type, resource_id)
        target = next((v for v in versions if v.version == target_version), None)
        if not target:
            raise ValueError(f"Version {target_version} not found for {resource_id}")
        for v in versions:
            v.promoted = v.version == target_version
            await self.storage.save_version(v)
        return {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "rolled_back_to": target_version,
            "content": target.content,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def list_versions(self, resource_type: str, resource_id: str) -> list[VersionRecord]:
        return await self.storage.list_versions(resource_type, resource_id)

    async def auto_rollback_on_regression(
        self, resource_type: str, resource_id: str, current_version: str, previous_version: str
    ) -> dict | None:
        versions = await self.storage.list_versions(resource_type, resource_id)
        current = next((v for v in versions if v.version == current_version), None)
        if current and current.promoted:
            return await self.rollback(resource_type, resource_id, previous_version)
        return None
