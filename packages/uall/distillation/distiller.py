import uuid

from uall_core.ports.storage import StoragePort
from uall_core.providers.heuristic import HeuristicLLMProvider, cosine_similarity
from uall_core.schemas.graph import GraphEdgeType, KnowledgeGraph
from uall_core.schemas.lesson import CandidateLesson, Lesson
from uall_core.schemas.namespace import ConfidenceDimensions, FreshnessMetrics, Provenance


class KnowledgeDistiller:
    def __init__(self, storage: StoragePort, llm: HeuristicLLMProvider | None = None):
        self.storage = storage
        self.llm = llm or HeuristicLLMProvider()
        self.merge_threshold = 0.92

    async def find_merge_target(self, candidate: CandidateLesson) -> tuple[str | None, float]:
        emb = await self.llm.embed(f"{candidate.root_cause} {candidate.fix}")
        best_id, best_sim = None, 0.0
        for lesson in await self.storage.list_lessons("active"):
            lesson_emb = lesson.embedding or await self.llm.embed(lesson.to_search_text())
            sim = cosine_similarity(emb, lesson_emb)
            if sim > best_sim:
                best_sim, best_id = sim, lesson.lesson_id
        if best_sim >= self.merge_threshold:
            return best_id, best_sim
        return None, best_sim

    async def merge_into_lesson(self, lesson_id: str, candidate: CandidateLesson) -> Lesson:
        lesson = await self.storage.get_lesson(lesson_id)
        if not lesson:
            raise ValueError(f"Lesson {lesson_id} not found")
        lesson.occurrence_count += 1
        lesson.confidence.evidence = min(1.0, lesson.confidence.evidence + 0.02)
        lesson.confidence.recalculate_overall()
        lesson.freshness.last_confirmed = lesson.freshness.created_at
        await self.storage.update_lesson(lesson)
        return lesson

    async def candidate_to_lesson(
        self,
        candidate: CandidateLesson,
        policy_version: str | None = None,
        validator_action: str = "approve",
    ) -> Lesson:
        embedding = await self.llm.embed(f"{candidate.root_cause} {candidate.fix}")
        lesson_id = f"lesson_{uuid.uuid4().hex[:8]}"
        confidence = ConfidenceDimensions(
            evidence=candidate.confidence,
            retrieval_success=0.5,
            human_verified=False,
        )
        confidence.recalculate_overall()
        graph = KnowledgeGraph(lesson_id=lesson_id)
        for eid in candidate.event_ids:
            if eid.startswith("failure"):
                graph.add_edge(GraphEdgeType.CAUSED_BY, eid)
            if eid.startswith("correction"):
                graph.add_edge(GraphEdgeType.FIXED_BY, eid)
        return Lesson(
            lesson_id=lesson_id,
            failure=candidate.failure,
            root_cause=candidate.root_cause,
            fix=candidate.fix,
            memory_type=candidate.memory_type,
            stage=candidate.stage,
            namespace=candidate.namespace,
            confidence=confidence,
            freshness=FreshnessMetrics(),
            provenance=Provenance(
                run_id=candidate.run_id,
                reflection_id=candidate.reflection_id,
                event_ids=candidate.event_ids,
                policy_version=policy_version,
                validator_action=validator_action,
                promoted_at=__import__("datetime").datetime.utcnow(),
            ),
            graph=graph,
            embedding=embedding,
            quality_score=0.7,
        )
