import re
import uuid
from datetime import datetime

from uall_core.ports.storage import StoragePort
from uall_core.providers.heuristic import HeuristicLLMProvider
from uall_core.schemas.lesson import CandidateLesson, Reflection


class ReflectionEngine:
    def __init__(self, storage: StoragePort, llm: HeuristicLLMProvider | None = None):
        self.storage = storage
        self.llm = llm or HeuristicLLMProvider()

    async def reflect(self, candidate: CandidateLesson) -> Reflection:
        prompt = (
            f"Analyze this agent failure and produce a lesson.\n"
            f"FAILURE: {candidate.failure}\n"
            f"CONTEXT: {candidate.evidence_payload}\n"
            f"Provide FAILURE, ROOT_CAUSE, FIX, CONFIDENCE."
        )
        response = await self.llm.complete(prompt)
        failure, root, fix, confidence = _parse_reflection(response, candidate)
        reflection = Reflection(
            reflection_id=f"reflection_{uuid.uuid4().hex[:8]}",
            failure=failure,
            root_cause=root,
            fix=fix,
            confidence=confidence,
            memory_type=candidate.memory_type,
            run_id=candidate.run_id,
            event_ids=candidate.event_ids,
        )
        await self.storage.save_reflection(reflection.model_dump(mode="json"))
        return reflection

    async def reflect_from_candidate(self, candidate: CandidateLesson) -> CandidateLesson:
        reflection = await self.reflect(candidate)
        return CandidateLesson(
            reflection_id=reflection.reflection_id,
            failure=reflection.failure,
            root_cause=reflection.root_cause,
            fix=reflection.fix,
            memory_type=reflection.memory_type,
            stage=candidate.stage,
            namespace=candidate.namespace,
            confidence=reflection.confidence,
            run_id=reflection.run_id,
            event_ids=reflection.event_ids,
            evidence_payload=candidate.evidence_payload,
        )


def _parse_reflection(response: str, candidate: CandidateLesson) -> tuple[str, str, str, float]:
    failure = candidate.failure
    root = candidate.root_cause or "Unknown root cause"
    fix = candidate.fix or "Add validation step"
    confidence = 0.8
    for line in response.splitlines():
        upper = line.upper()
        if "FAILURE:" in upper:
            failure = line.split(":", 1)[1].strip()
        elif "ROOT_CAUSE:" in upper or "ROOT CAUSE:" in upper:
            root = line.split(":", 1)[1].strip()
        elif "FIX:" in upper:
            fix = line.split(":", 1)[1].strip()
        elif "CONFIDENCE:" in upper:
            try:
                confidence = float(re.findall(r"[\d.]+", line)[0])
            except (IndexError, ValueError):
                pass
    return failure[:300], root[:300], fix[:300], min(max(confidence, 0.0), 1.0)
