from collections import Counter

from uall_core.ports.storage import StoragePort
from uall_core.schemas.lesson import MemorySearchRequest


class RecommendationEngine:
    def __init__(self, storage: StoragePort):
        self.storage = storage

    async def get_recommendations(
        self,
        agent_id: str | None = None,
        workflow_id: str | None = None,
        context: str | None = None,
    ) -> list[dict]:
        lessons = await self.storage.list_lessons("active")
        recs = []
        for lesson in lessons:
            if lesson.occurrence_count < 1:
                continue
            if lesson.confidence.overall < 0.5:
                continue
            if workflow_id and lesson.stage.workflow and lesson.stage.workflow != workflow_id:
                continue
            if agent_id and lesson.stage.agent and lesson.stage.agent != agent_id:
                continue
            impact = lesson.occurrence_count * lesson.confidence.overall
            recs.append(
                {
                    "type": "prompt_recommendation",
                    "lesson_id": lesson.lesson_id,
                    "text": lesson.fix,
                    "confidence": lesson.confidence.overall,
                    "observed_over": lesson.occurrence_count,
                    "estimated_impact": f"Reduce failures by ~{int(impact * 3)}%",
                    "workflow": lesson.stage.workflow,
                    "step": lesson.stage.step,
                }
            )
        recs.sort(key=lambda x: x["confidence"] * x["observed_over"], reverse=True)
        return recs[:10]


class PatternDetector:
    def __init__(self, storage: StoragePort):
        self.storage = storage
        self.threshold = 3

    async def detect_patterns(self) -> list[dict]:
        lessons = await self.storage.list_lessons("active")
        causes = Counter()
        for lesson in lessons:
            key = lesson.root_cause[:80] if lesson.root_cause else lesson.failure[:80]
            causes[key] += lesson.occurrence_count
        patterns = []
        for cause, count in causes.most_common():
            if count >= self.threshold:
                patterns.append(
                    {
                        "pattern": cause,
                        "occurrences": count,
                        "recommendation": f"Address recurring issue: {cause}",
                    }
                )
        return patterns
