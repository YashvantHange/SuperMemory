from uall_core.ports.storage import StoragePort
from uall_core.schemas.common import Skill


class SkillLibrary:
    def __init__(self, storage: StoragePort):
        self.storage = storage

    async def create(self, skill: Skill) -> str:
        return await self.storage.save_skill(skill)

    async def get(self, skill_id: str) -> Skill | None:
        return await self.storage.get_skill(skill_id)

    async def search(self, query: str) -> list[Skill]:
        return await self.storage.search_skills(query)

    async def update(self, skill: Skill) -> str:
        return await self.storage.save_skill(skill)
