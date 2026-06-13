from uall_core.ports.storage import StoragePort
from uall_core.schemas.common import PolicyVersion
from uall_core.schemas.lesson import Lesson


class PolicyManager:
    def __init__(self, storage: StoragePort):
        self.storage = storage

    async def get_active(self) -> list[PolicyVersion]:
        policies = await self.storage.get_active_policies()
        if not policies:
            default = PolicyVersion(
                policy_id="security_policy",
                version="v1",
                rules=[
                    "Never expose secrets in output",
                    "Prefer inspecting document structure before OCR",
                ],
            )
            await self.storage.save_policy(default)
            return [default]
        return policies

    async def create_policy(self, policy: PolicyVersion) -> str:
        return await self.storage.save_policy(policy)

    async def list_versions(self, policy_id: str) -> list[PolicyVersion]:
        return await self.storage.list_policy_versions(policy_id)

    async def get_active_version_string(self) -> str:
        policies = await self.get_active()
        if policies:
            return f"{policies[0].policy_id}:{policies[0].version}"
        return "none"

    async def flag_lessons_for_revalidation(self, old_version: str) -> list[str]:
        flagged = []
        for lesson in await self.storage.list_lessons("active"):
            if lesson.provenance.policy_version == old_version:
                lesson.status = "pending_revalidation"
                await self.storage.update_lesson(lesson)
                flagged.append(lesson.lesson_id)
        return flagged
