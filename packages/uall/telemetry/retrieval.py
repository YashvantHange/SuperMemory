from datetime import datetime

from uall_core.ports.storage import StoragePort
from uall_core.schemas.common import RetrievalTelemetryEvent
from uall.memory.confidence import update_from_telemetry


class RetrievalTelemetryService:
    def __init__(self, storage: StoragePort):
        self.storage = storage

    async def record_outcome(
        self,
        telemetry_id: str | None,
        lesson_id: str,
        run_id: str | None = None,
        used: bool = False,
        accepted: bool = False,
        improved: bool | None = None,
    ) -> dict:
        event = RetrievalTelemetryEvent(
            telemetry_id=telemetry_id or f"tel_{lesson_id}_{datetime.utcnow().timestamp():.0f}",
            lesson_id=lesson_id,
            run_id=run_id,
            retrieved=True,
            used=used,
            accepted=accepted,
            outcome_improved=improved,
        )
        await self.storage.save_telemetry(event)

        lesson = await self.storage.get_lesson(lesson_id)
        if lesson:
            update_from_telemetry(lesson, used, accepted, improved)
            await self.storage.update_lesson(lesson)

        return {"telemetry_id": event.telemetry_id, "recorded": True}

    async def list_for_lesson(self, lesson_id: str) -> list[RetrievalTelemetryEvent]:
        return await self.storage.list_telemetry(lesson_id)
