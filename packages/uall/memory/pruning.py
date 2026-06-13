from uall_core.ports.storage import StoragePort
from uall_core.providers.heuristic import cosine_similarity, HeuristicLLMProvider
from uall.memory.freshness import compute_staleness


class MemoryPruner:
    def __init__(self, storage: StoragePort, llm: HeuristicLLMProvider | None = None):
        self.storage = storage
        self.llm = llm or HeuristicLLMProvider()

    async def prune(self) -> dict:
        merged = await self._merge_duplicates()
        archived = await self._archive_stale()
        removed = await self._remove_low_value()
        return {"merged": merged, "archived": archived, "removed": removed}

    async def _merge_duplicates(self) -> int:
        lessons = await self.storage.list_lessons("active")
        count = 0
        seen: set[str] = set()
        for i, a in enumerate(lessons):
            if a.lesson_id in seen:
                continue
            for b in lessons[i + 1 :]:
                if b.lesson_id in seen:
                    continue
                emb_a = a.embedding or await self.llm.embed(a.to_search_text())
                emb_b = b.embedding or await self.llm.embed(b.to_search_text())
                if cosine_similarity(emb_a, emb_b) > 0.95:
                    a.occurrence_count += b.occurrence_count
                    await self.storage.update_lesson(a)
                    b.status = "archived"
                    await self.storage.update_lesson(b)
                    seen.add(b.lesson_id)
                    count += 1
        return count

    async def _archive_stale(self) -> int:
        count = 0
        for lesson in await self.storage.list_lessons("active"):
            lesson.freshness.staleness_score = compute_staleness(lesson)
            if lesson.freshness.staleness_score > 0.8 and lesson.freshness.usage_count < 3:
                lesson.status = "archived"
                await self.storage.update_lesson(lesson)
                count += 1
        return count

    async def _remove_low_value(self) -> int:
        count = 0
        for lesson in await self.storage.list_lessons("active"):
            if lesson.quality_score < 0.3 and lesson.freshness.usage_count == 0:
                lesson.status = "archived"
                await self.storage.update_lesson(lesson)
                count += 1
        return count
