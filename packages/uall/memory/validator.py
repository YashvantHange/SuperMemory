from uall_core.ports.storage import StoragePort
from uall_core.providers.heuristic import HeuristicLLMProvider
from uall_core.schemas.common import PolicyVersion
from uall_core.schemas.lesson import CandidateLesson, ValidationResult


class MemoryValidator:
    def __init__(self, storage: StoragePort, llm: HeuristicLLMProvider | None = None):
        self.storage = storage
        self.llm = llm or HeuristicLLMProvider()
        self.min_quality = 0.4

    async def validate(self, candidate: CandidateLesson) -> ValidationResult:
        quality = await self._score_quality(candidate)
        policies = await self.storage.get_active_policies()

        if not self._has_evidence(candidate):
            return ValidationResult(
                action="reject",
                candidate=candidate,
                quality_score=quality,
                reason="No evidence in event payload",
            )

        for policy in policies:
            if await self._contradicts_policy(candidate, policy):
                return ValidationResult(
                    action="reject",
                    candidate=candidate,
                    quality_score=quality,
                    reason=f"Contradicts policy {policy.policy_id} v{policy.version}",
                )

        merge_id, sim = await self._find_duplicate(candidate)
        if merge_id:
            return ValidationResult(
                action="merge",
                candidate=candidate,
                quality_score=quality,
                merge_target_id=merge_id,
                reason=f"Near-duplicate similarity {sim:.2f}",
            )

        conflict = await self._find_conflict(candidate)
        if conflict:
            return ValidationResult(
                action="reject",
                candidate=candidate,
                quality_score=quality,
                reason=f"Conflicts with lesson {conflict}",
            )

        if quality < self.min_quality:
            return ValidationResult(
                action="reject",
                candidate=candidate,
                quality_score=quality,
                reason=f"Quality score {quality:.2f} below threshold",
            )

        if len(candidate.fix) < 20 or not any(
            w in candidate.fix.lower() for w in ("verify", "check", "inspect", "validate", "use", "before", "first")
        ):
            rewritten = await self._rewrite(candidate)
            return ValidationResult(
                action="rewrite",
                candidate=candidate,
                quality_score=quality,
                rewritten_fix=rewritten,
                reason="Rewritten for clarity and actionability",
            )

        return ValidationResult(
            action="approve",
            candidate=candidate,
            quality_score=quality,
            reason="Passed all validation checks",
        )

    async def _score_quality(self, candidate: CandidateLesson) -> float:
        score = 0.3
        if candidate.failure:
            score += 0.15
        if candidate.root_cause and len(candidate.root_cause) > 10:
            score += 0.2
        if candidate.fix and len(candidate.fix) > 15:
            score += 0.25
        if candidate.evidence_payload:
            score += 0.1
        return min(1.0, score)

    def _has_evidence(self, candidate: CandidateLesson) -> bool:
        if candidate.event_ids:
            return True
        if candidate.failure and candidate.failure.strip():
            return True
        if candidate.fix and len(candidate.fix.strip()) > 10:
            return True
        payload = candidate.evidence_payload or {}
        snippet = payload.get("snippet") or payload.get("after") or payload.get("intent")
        return bool(snippet and str(snippet).strip())

    async def _contradicts_policy(self, candidate: CandidateLesson, policy: PolicyVersion) -> bool:
        fix_lower = candidate.fix.lower()
        for rule in policy.rules:
            rule_lower = rule.lower()
            if "never expose secrets" in rule_lower and "secret" in fix_lower:
                if "never" not in fix_lower and "don't" not in fix_lower:
                    return True
        return False

    async def _find_duplicate(self, candidate: CandidateLesson) -> tuple[str | None, float]:
        from uall_core.providers.heuristic import cosine_similarity

        emb = await self.llm.embed(f"{candidate.root_cause} {candidate.fix}")
        best_id, best_sim = None, 0.0
        for lesson in await self.storage.list_lessons("active"):
            lesson_emb = lesson.embedding or await self.llm.embed(lesson.to_search_text())
            sim = cosine_similarity(emb, lesson_emb)
            if sim > best_sim:
                best_sim, best_id = sim, lesson.lesson_id
        if best_sim >= 0.92:
            return best_id, best_sim
        return None, best_sim

    async def _find_conflict(self, candidate: CandidateLesson) -> str | None:
        for lesson in await self.storage.list_lessons("active"):
            if lesson.graph:
                conflicts = lesson.graph.get_targets(
                    __import__(
                        "uall_core.schemas.graph", fromlist=["GraphEdgeType"]
                    ).GraphEdgeType.CONFLICTS_WITH
                )
                if candidate.reflection_id in conflicts:
                    return lesson.lesson_id
        return None

    async def _rewrite(self, candidate: CandidateLesson) -> str:
        prompt = f"Rewrite this fix to be actionable: {candidate.fix}"
        response = await self.llm.complete(prompt)
        for line in response.splitlines():
            if "FIX:" in line.upper():
                return line.split(":", 1)[1].strip()
        return f"Before acting: validate. {candidate.fix}"
