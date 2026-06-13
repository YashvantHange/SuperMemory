from uall_core.ports.storage import StoragePort
from uall.evaluation.engine import EvaluationEngine
from uall.recommendations.engine import PatternDetector


class AnalyticsService:
    def __init__(self, storage: StoragePort):
        self.storage = storage
        self.evaluator = EvaluationEngine(storage)

    async def get_analytics(self) -> dict:
        runs = await self.storage.list_runs()
        lessons = await self.storage.list_lessons("active")
        successes = sum(1 for r in runs if r.get("success"))
        total = len(runs) or 1
        return {
            "total_runs": len(runs),
            "success_rate": round(successes / total, 3),
            "active_lessons": len(lessons),
            "avg_lesson_confidence": round(
                sum(l.confidence.overall for l in lessons) / max(len(lessons), 1), 3
            ),
            "memory_health": "good" if len(lessons) < 1000 else "review_pruning",
        }

    async def workflow_health(self, workflow_id: str) -> dict:
        from uall.optimization.optimizers import WorkflowOptimizer

        opt = WorkflowOptimizer(self.storage)
        return await opt.analyze(workflow_id)

    async def top_failures(self, limit: int = 10) -> list[dict]:
        detector = PatternDetector(self.storage)
        patterns = await detector.detect_patterns()
        return patterns[:limit]
