from uall_core.ports.storage import StoragePort


class EvaluationEngine:
    def __init__(self, storage: StoragePort):
        self.storage = storage

    async def evaluate_run(self, run_id: str) -> dict:
        run = await self.storage.get_run(run_id)
        if not run:
            return {"error": "run not found"}
        events = run.get("events", [])
        failures = sum(1 for e in events if e.get("event_type") == "failure")
        corrections = sum(1 for e in events if e.get("event_type") == "correction")
        success = run.get("success", False)
        score = 1.0 if success else 0.0
        score -= failures * 0.15
        score -= corrections * 0.1
        score = max(0.0, min(1.0, score))
        return {
            "run_id": run_id,
            "score": round(score, 3),
            "success": success,
            "failures": failures,
            "corrections": corrections,
            "retry_count": failures,
            "human_intervention": corrections > 0,
        }

    async def agent_score(self, agent_id: str | None = None) -> dict:
        runs = await self.storage.list_runs()
        scores = []
        for run in runs:
            ev = await self.evaluate_run(run.get("run_id", ""))
            if "score" in ev:
                scores.append(ev["score"])
        avg = sum(scores) / len(scores) if scores else 0.0
        return {"agent_id": agent_id, "average_score": round(avg, 3), "run_count": len(scores)}
