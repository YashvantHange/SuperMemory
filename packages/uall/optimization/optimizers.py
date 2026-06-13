from uall_core.ports.storage import StoragePort


class PromptOptimizer:
    def __init__(self, storage: StoragePort):
        self.storage = storage

    async def suggest(self, agent_id: str, step: str, current_prompt: str) -> dict:
        from uall.recommendations.engine import RecommendationEngine

        recs = RecommendationEngine(self.storage)
        recommendations = await recs.get_recommendations(agent_id=agent_id)
        additions = [r["text"] for r in recommendations if r.get("step") == step][:3]
        if not additions:
            additions = [r["text"] for r in recommendations[:2]]
        suggested = current_prompt
        if additions:
            suggested += "\n\n[UALL Recommendations]\n" + "\n".join(f"- {a}" for a in additions)
        return {
            "agent_id": agent_id,
            "step": step,
            "current": current_prompt,
            "recommended": suggested,
            "additions": additions,
            "confidence": recommendations[0]["confidence"] if recommendations else 0.0,
        }


class WorkflowOptimizer:
    def __init__(self, storage: StoragePort):
        self.storage = storage

    async def analyze(self, workflow_id: str) -> dict:
        runs = await self.storage.list_runs()
        step_failures: dict[str, int] = {}
        for run in runs:
            if run.get("workflow_id") != workflow_id:
                continue
            for evt in run.get("events", []):
                if evt.get("event_type") == "failure":
                    step = evt.get("stage", {}).get("step", "unknown")
                    step_failures[step] = step_failures.get(step, 0) + 1
        suggestions = []
        if step_failures:
            worst = max(step_failures, key=step_failures.get)
            suggestions.append(
                {
                    "type": "workflow_reorder",
                    "message": f"Add validation before '{worst}' step",
                    "high_failure_step": worst,
                    "failure_count": step_failures[worst],
                }
            )
        return {
            "workflow_id": workflow_id,
            "step_failures": step_failures,
            "health": "degraded" if step_failures else "healthy",
            "suggestions": suggestions,
        }
