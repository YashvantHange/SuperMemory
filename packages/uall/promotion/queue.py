import uuid
from datetime import datetime

from uall_core.ports.storage import StoragePort
from uall_core.schemas.lesson import CandidateLesson, PendingLesson, ValidationResult
from uall.distillation.distiller import KnowledgeDistiller
from uall.memory.policies import PolicyManager
from uall.memory.provenance import attach_provenance


class PromotionQueue:
    def __init__(self, storage: StoragePort, distiller: KnowledgeDistiller, policies: PolicyManager):
        self.storage = storage
        self.distiller = distiller
        self.policies = policies

    async def enqueue(self, candidate: CandidateLesson, validation: ValidationResult) -> str:
        pending = PendingLesson(
            pending_id=f"pending_{uuid.uuid4().hex[:8]}",
            candidate=candidate,
            validation_result=validation,
            status="pending",
        )
        await self.storage.save_pending(pending)
        return pending.pending_id

    async def list_pending(self, status: str = "pending") -> list[PendingLesson]:
        return await self.storage.list_pending(status)

    async def process_queue(self, limit: int = 50) -> dict:
        pending_list = (await self.storage.list_pending("pending"))[:limit]
        promoted: list[str] = []
        discarded: list[str] = []
        merged: list[str] = []

        for pending in pending_list:
            pending.status = "evaluating"
            await self.storage.update_pending(pending)
            result, lesson_id = await self._process_one(pending)
            if result == "promoted" and lesson_id:
                promoted.append(lesson_id)
            elif result == "merged" and lesson_id:
                merged.append(lesson_id)
            else:
                discarded.append(pending.pending_id)

        return {
            "promoted": promoted,
            "discarded": discarded,
            "merged": merged,
            "processed": len(pending_list),
        }

    async def _process_one(self, pending: PendingLesson) -> tuple[str, str | None]:
        validation = pending.validation_result
        candidate = pending.candidate

        if validation.action == "reject":
            pending.status = "discarded"
            pending.processed_at = datetime.utcnow()
            await self.storage.update_pending(pending)
            return "discarded", None

        if validation.action == "merge" and validation.merge_target_id:
            await self.distiller.merge_into_lesson(validation.merge_target_id, candidate)
            pending.status = "promoted"
            pending.processed_at = datetime.utcnow()
            await self.storage.update_pending(pending)
            return "merged", validation.merge_target_id

        if validation.action == "rewrite" and validation.rewritten_fix:
            candidate.fix = validation.rewritten_fix

        # Shadow test: simple heuristic — fix must be actionable
        if not await self._shadow_test(candidate):
            pending.status = "discarded"
            pending.processed_at = datetime.utcnow()
            await self.storage.update_pending(pending)
            return "discarded", None

        policy_version = await self.policies.get_active_version_string()
        lesson = await self.distiller.candidate_to_lesson(
            candidate,
            policy_version=policy_version,
            validator_action=validation.action,
        )
        lesson.quality_score = validation.quality_score
        attach_provenance(
            lesson,
            run_id=candidate.run_id,
            reflection_id=candidate.reflection_id,
            event_ids=candidate.event_ids,
            policy_version=policy_version,
            validator_action=validation.action,
        )
        await self.storage.save_lesson(lesson)
        pending.status = "promoted"
        pending.processed_at = datetime.utcnow()
        await self.storage.update_pending(pending)
        return "promoted", lesson.lesson_id

    async def _shadow_test(self, candidate: CandidateLesson) -> bool:
        if len(candidate.fix) < 10:
            return False
        if not candidate.root_cause:
            return False
        return True
