import os
import uuid
from datetime import datetime

from uall_core.ports.storage import StoragePort
from uall_core.providers.heuristic import HeuristicLLMProvider
from uall_core.schemas.events import Event, EventType, Feedback, RunEnd, RunStart, StageMetadata
from uall_core.schemas.lesson import CandidateLesson


class EventCollector:
    def __init__(self, storage: StoragePort):
        self.storage = storage

    async def start_run(self, data: RunStart) -> dict:
        await self.storage.save_run_start(data)
        event = Event(
            event_id=f"evt_{uuid.uuid4().hex[:8]}",
            event_type=EventType.WORKFLOW_START,
            run_id=data.run_id,
            stage=data.stage,
            payload={"workflow_id": data.workflow_id, "agents": data.agents},
        )
        await self.storage.save_event(event)
        return {"run_id": data.run_id, "status": "started"}

    async def record_event(self, event: Event) -> dict:
        await self.storage.save_event(event)
        return {"event_id": event.event_id, "recorded": True}

    async def end_run(self, data: RunEnd) -> dict:
        await self.storage.save_run_end(data)
        event = Event(
            event_id=f"evt_{uuid.uuid4().hex[:8]}",
            event_type=EventType.WORKFLOW_END,
            run_id=data.run_id,
            payload={"success": data.success, "metrics": data.metrics},
        )
        await self.storage.save_event(event)
        return {"run_id": data.run_id, "status": "ended", "success": data.success}

    async def record_feedback(self, feedback: Feedback) -> dict:
        fid = await self.storage.save_feedback(feedback)
        return {"feedback_id": fid}

    def event_from_failure(
        self,
        run_id: str,
        snippet: str,
        stage: StageMetadata,
        tags: list[str] | None = None,
    ) -> Event:
        return Event(
            event_id=f"failure_{uuid.uuid4().hex[:8]}",
            event_type=EventType.FAILURE,
            run_id=run_id,
            stage=stage,
            tags=tags or [],
            payload={"snippet": snippet[:500]},
        )

    def event_from_correction(
        self,
        run_id: str,
        before: str,
        after: str,
        intent: str,
        stage: StageMetadata,
    ) -> Event:
        return Event(
            event_id=f"correction_{uuid.uuid4().hex[:8]}",
            event_type=EventType.CORRECTION,
            run_id=run_id,
            stage=stage,
            payload={"before": before[:300], "after": after[:300], "intent": intent},
        )

    async def get_candidates_from_run(self, run_id: str) -> list[CandidateLesson]:
        run = await self.storage.get_run(run_id)
        if not run:
            return []
        candidates = []
        for evt in run.get("events", []):
            if evt.get("event_type") in ("failure", "correction", "suggestion"):
                stage = StageMetadata(**evt.get("stage", {}))
                payload = evt.get("payload", {})
                snippet = payload.get("snippet") or payload.get("intent") or ""
                candidates.append(
                    CandidateLesson(
                        reflection_id="",
                        failure=snippet,
                        root_cause=payload.get("intent", ""),
                        fix=payload.get("after", snippet),
                        stage=stage,
                        run_id=run_id,
                        event_ids=[evt.get("event_id", "")],
                        evidence_payload=payload,
                    )
                )
        return candidates
