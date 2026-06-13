import uuid
from datetime import datetime

from uall_core.ports.storage import StoragePort
from uall_core.providers.heuristic import HeuristicLLMProvider, cosine_similarity
from uall_core.schemas.common import PolicyVersion, RetrievalTelemetryEvent
from uall_core.schemas.lesson import Lesson, MemorySearchRequest, MemorySearchResult
from uall.memory.freshness import freshness_weight
from uall.memory.namespaces import namespace_match_score, parse_namespace
from uall.memory.ttl import is_expired, ttl_weight


class MemoryRetriever:
    """Hybrid multi-stage retrieval pipeline."""

    def __init__(self, storage: StoragePort, llm: HeuristicLLMProvider | None = None):
        self.storage = storage
        self.llm = llm or HeuristicLLMProvider()

    async def retrieve(self, request: MemorySearchRequest) -> list[MemorySearchResult]:
        # Stage 1: policies (injected first, not ranked)
        policies = await self.storage.get_active_policies()
        policy_text = self._format_policies(policies)

        # Stage 2: namespace + metadata filter via storage
        candidates = await self.storage.search_lessons(request)

        # Stage 3: vector similarity scoring
        query_emb = await self.llm.embed(request.query)
        query_ns = parse_namespace(request.namespace)

        scored: list[tuple[float, Lesson]] = []
        for lesson in candidates:
            if is_expired(lesson):
                continue
            emb = lesson.embedding or await self.llm.embed(lesson.to_search_text())
            semantic = cosine_similarity(query_emb, emb)
            stage_boost = self._stage_boost(lesson, request)
            ns_boost = namespace_match_score(lesson.namespace, query_ns)
            fresh_w = freshness_weight(lesson)
            ttl_w = ttl_weight(lesson)
            conf_w = lesson.confidence.overall
            final = semantic * stage_boost * ns_boost * fresh_w * ttl_w * conf_w
            scored.append((final, lesson))

        # Stage 4: rerank top candidates (lightweight sort)
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[: request.top_k]

        results = []
        token_budget = request.max_tokens
        policy_tokens = len(policy_text.split())
        token_budget -= policy_tokens

        for score, lesson in top:
            text = f"- {lesson.fix}"
            tokens = len(text.split())
            if token_budget <= 0:
                break
            tid = f"tel_{uuid.uuid4().hex[:8]}"
            await self.storage.save_telemetry(
                RetrievalTelemetryEvent(
                    telemetry_id=tid,
                    lesson_id=lesson.lesson_id,
                    retrieved=True,
                )
            )
            results.append(MemorySearchResult(lesson=lesson, score=score, telemetry_id=tid))
            token_budget -= tokens

        if policy_text and results:
            # Attach policy context to first result metadata
            results[0].lesson.metadata["policy_prefix"] = policy_text

        return results

    def _stage_boost(self, lesson: Lesson, request: MemorySearchRequest) -> float:
        boost = 0.1
        if request.step and lesson.stage.step == request.step:
            boost = 1.0
        elif request.workflow and lesson.stage.workflow == request.workflow:
            boost = 0.6
        elif request.domain and lesson.stage.domain == request.domain:
            boost = 0.3
        if request.tool and lesson.stage.tool == request.tool:
            boost = max(boost, 0.8)
        if request.agent and lesson.stage.agent == request.agent:
            boost = max(boost, 0.9)
        return boost

    def _format_policies(self, policies: list[PolicyVersion]) -> str:
        if not policies:
            return ""
        lines = ["[ORG POLICIES]"]
        for p in policies:
            for rule in p.rules:
                lines.append(f"- {rule}")
        return "\n".join(lines)
