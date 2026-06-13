"""Central UALL orchestrator — closed-loop learning cycle."""

import uuid
from datetime import datetime

from uall.analytics.service import AnalyticsService
from uall.collector.service import EventCollector
from uall.distillation.distiller import KnowledgeDistiller
from uall.evaluation.engine import EvaluationEngine
from uall.experiments.manager import ExperimentManager
from uall.memory.graph import graph_to_dict
from uall.memory.policies import PolicyManager
from uall.memory.pruning import MemoryPruner
from uall.memory.retrieval import MemoryRetriever
from uall.memory.validator import MemoryValidator
from uall.optimization.optimizers import PromptOptimizer, WorkflowOptimizer
from uall.promotion.queue import PromotionQueue
from uall.recommendations.engine import PatternDetector, RecommendationEngine
from uall.reflection.engine import ReflectionEngine
from uall.rollback.manager import RollbackManager
from uall.skills.library import SkillLibrary
from uall.telemetry.retrieval import RetrievalTelemetryService
from uall_core.ports.storage import StoragePort
from uall_core.providers.heuristic import HeuristicLLMProvider
from uall_core.schemas.common import PolicyVersion, Skill
from uall_core.schemas.events import Event, EventType, Feedback, RunEnd, RunStart, StageMetadata
from uall_core.schemas.lesson import (
    CandidateLesson,
    Lesson,
    MemorySearchRequest,
    MemorySearchResult,
    ValidationResult,
)


class UALLService:
    def __init__(self, storage: StoragePort, llm: HeuristicLLMProvider | None = None):
        self.storage = storage
        self.llm = llm or HeuristicLLMProvider()
        self.collector = EventCollector(storage)
        self.reflection = ReflectionEngine(storage, self.llm)
        self.distiller = KnowledgeDistiller(storage, self.llm)
        self.validator = MemoryValidator(storage, self.llm)
        self.policies = PolicyManager(storage)
        self.promotion = PromotionQueue(storage, self.distiller, self.policies)
        self.retriever = MemoryRetriever(storage, self.llm)
        self.telemetry = RetrievalTelemetryService(storage)
        self.evaluator = EvaluationEngine(storage)
        self.recommendations = RecommendationEngine(storage)
        self.patterns = PatternDetector(storage)
        self.experiments = ExperimentManager(storage)
        self.rollback = RollbackManager(storage)
        self.skills = SkillLibrary(storage)
        self.pruner = MemoryPruner(storage, self.llm)
        self.prompt_optimizer = PromptOptimizer(storage)
        self.workflow_optimizer = WorkflowOptimizer(storage)
        self.analytics = AnalyticsService(storage)

    async def init(self) -> None:
        await self.storage.init()
        await self.policies.get_active()

    # --- Runs ---
    async def start_run(self, data: RunStart) -> dict:
        return await self.collector.start_run(data)

    async def record_event(self, event: Event, *, auto_learn: bool = False) -> dict:
        result = await self.collector.record_event(event)
        if auto_learn and event.event_type.value in ("failure", "correction", "suggestion"):
            await self._learning_pipeline_from_event(event)
        return result

    async def end_run(self, data: RunEnd) -> dict:
        result = await self.collector.end_run(data)
        eval_result = await self.evaluator.evaluate_run(data.run_id)
        result["evaluation"] = eval_result
        for lesson_id in data.lessons_used:
            await self.telemetry.record_outcome(
                telemetry_id=None,
                lesson_id=lesson_id,
                run_id=data.run_id,
                used=True,
                improved=data.success,
            )
        return result

    async def record_feedback(self, feedback: Feedback) -> dict:
        return await self.collector.record_feedback(feedback)

    # --- Learning pipeline ---
    async def _learning_pipeline_from_event(self, event: Event) -> None:
        candidate = CandidateLesson(
            reflection_id="",
            failure=event.payload.get("snippet", str(event.payload)[:200]),
            root_cause=event.payload.get("intent", ""),
            fix=event.payload.get("after", event.payload.get("snippet", "")),
            stage=event.stage,
            run_id=event.run_id,
            event_ids=[event.event_id],
            evidence_payload=event.payload,
        )
        await self.reflect_and_queue(candidate, auto_promote=True)

    async def reflect_and_queue(
        self, candidate: CandidateLesson, *, auto_promote: bool = False
    ) -> dict:
        if not self.validator._has_evidence(candidate):
            return {"status": "rejected", "reason": "No evidence in event payload"}
        candidate = await self.reflection.reflect_from_candidate(candidate)
        validation = await self.validator.validate(candidate)
        if validation.action == "reject":
            return {"status": "rejected", "reason": validation.reason}
        pending_id = await self.promotion.enqueue(candidate, validation)
        result: dict = {"status": "queued", "pending_id": pending_id, "reflection_id": candidate.reflection_id}
        if auto_promote:
            result["promotion"] = await self.process_promotion_queue()
        return result

    async def validate_lesson(self, candidate: CandidateLesson) -> ValidationResult:
        return await self.validator.validate(candidate)

    async def process_promotion_queue(self, limit: int = 50) -> dict:
        return await self.promotion.process_queue(limit=limit)

    async def record_mcp_event(
        self,
        event_type: str,
        summary: str,
        *,
        workflow: str | None = None,
        step: str | None = None,
        tool: str | None = None,
        agent: str | None = None,
        domain: str | None = None,
        language: str | None = None,
        environment: str | None = None,
        namespace: str = "global",
        payload: dict | None = None,
    ) -> dict:
        ns_level, ns_id = _parse_namespace_string(namespace)
        stage = StageMetadata(
            workflow=workflow,
            step=step,
            tool=tool,
            agent=agent,
            domain=domain,
            language=language,
            environment=environment,
            namespace=ns_level,
            namespace_id=ns_id,
        )
        run_id = f"mcp_{uuid.uuid4().hex[:8]}"
        etype = EventType(event_type) if event_type in EventType._value2member_map_ else EventType.FAILURE
        event = Event(
            event_id=f"event_{uuid.uuid4().hex[:8]}",
            event_type=etype,
            run_id=run_id,
            stage=stage,
            payload={"summary": summary[:800], **(payload or {})},
        )
        await self.collector.record_event(event)
        return {
            "id": event.event_id,
            "type": event_type,
            "summary": summary[:800],
            "metadata": {
                "workflow": workflow,
                "step": step,
                "tool": tool,
                "agent": agent,
                "domain": domain,
                "language": language,
                "environment": environment,
                "namespace": namespace,
            },
        }

    async def reflect_from_events(
        self,
        event_ids: list[str],
        suggestion: str | None = None,
        lesson_text: str | None = None,
    ) -> dict:
        events = []
        for event_id in event_ids:
            evt = await self.storage.get_event(event_id)
            if evt:
                events.append(evt)
        if not events:
            raise ValueError("Reflection requires at least one existing event_id")

        stage = _stage_from_events(events)
        summaries = [
            evt.get("payload", {}).get("summary")
            or evt.get("payload", {}).get("snippet")
            or str(evt.get("payload", {}))[:200]
            for evt in events
        ]
        failure = summaries[0][:300]
        fix = lesson_text or suggestion or f"Address: {failure[:200]}"
        if suggestion and not lesson_text:
            fix = f"When this pattern appears, apply this fix: {suggestion[:500]}"
        candidate = CandidateLesson(
            reflection_id="",
            failure=failure,
            root_cause=suggestion or "Derived from recorded evidence",
            fix=fix[:300],
            stage=stage,
            run_id=events[0].get("run_id"),
            event_ids=[evt.get("event_id", "") for evt in events],
            evidence_payload={"summaries": summaries, "suggestion": suggestion},
        )
        candidate = await self.reflection.reflect_from_candidate(candidate)
        return {
            "id": candidate.reflection_id,
            "candidate_lesson": candidate.fix,
            "event_ids": candidate.event_ids,
            "metadata": {
                "workflow": stage.workflow,
                "step": stage.step,
                "namespace": _namespace_string(stage.namespace, stage.namespace_id),
            },
            "suggestion": suggestion,
            "status": "candidate",
        }

    async def validate_and_enqueue(
        self,
        reflection_id: str | None = None,
        candidate_lesson: str | None = None,
        event_ids: list[str] | None = None,
        metadata: dict | None = None,
    ) -> dict:
        reflection = await self.storage.get_reflection(reflection_id) if reflection_id else None
        text = candidate_lesson or (reflection or {}).get("fix")
        evidence_ids = event_ids or (reflection or {}).get("event_ids", [])
        if reflection and not text:
            text = reflection.get("fix")
        if not text:
            return {"action": "reject", "reason": "Candidate lesson is empty.", "quality_score": 0.0}

        events = []
        for event_id in evidence_ids:
            evt = await self.storage.get_event(event_id)
            if evt:
                events.append(evt)
        if not events:
            return {
                "action": "reject",
                "reason": "No durable evidence event supports this lesson.",
                "quality_score": 0.0,
            }
        stage = _stage_from_events(events)
        if metadata:
            ns_level, ns_id = _parse_namespace_string(metadata.get("namespace", "global"))
            stage = StageMetadata(
                workflow=metadata.get("workflow") or stage.workflow,
                step=metadata.get("step") or stage.step,
                namespace=ns_level,
                namespace_id=ns_id,
            )
        candidate = CandidateLesson(
            reflection_id=reflection_id or (reflection or {}).get("reflection_id", ""),
            failure=(reflection or {}).get("failure", text[:200]),
            root_cause=(reflection or {}).get("root_cause", ""),
            fix=text,
            stage=stage,
            run_id=(reflection or {}).get("run_id"),
            event_ids=[evt.get("event_id", "") for evt in events] or evidence_ids,
            evidence_payload={"summaries": [evt.get("payload", {}) for evt in events]},
        )
        validation = await self.validator.validate(candidate)
        result = {
            "action": validation.action,
            "quality_score": validation.quality_score,
            "reason": validation.reason,
        }
        if validation.action == "reject":
            return result
        if validation.action == "merge":
            result["target_id"] = validation.merge_target_id
            return result
        if validation.rewritten_fix:
            candidate.fix = validation.rewritten_fix
        pending_id = await self.promotion.enqueue(candidate, validation)
        result["pending_id"] = pending_id
        result["lesson"] = candidate.fix
        return result

    async def retrieve_for_mcp(
        self,
        query: str,
        *,
        workflow: str | None = None,
        step: str | None = None,
        tool: str | None = None,
        agent: str | None = None,
        domain: str | None = None,
        language: str | None = None,
        environment: str | None = None,
        namespace: str = "global",
        top_k: int = 5,
        max_tokens: int = 800,
    ) -> dict:
        ns_level, ns_id = _parse_namespace_string(namespace)
        req = MemorySearchRequest(
            query=query,
            workflow=workflow,
            step=step,
            tool=tool,
            agent=agent,
            domain=domain,
            namespace=ns_level,
            namespace_id=ns_id,
            top_k=top_k,
            max_tokens=max_tokens,
        )
        results = await self.retriever.retrieve(req)
        policies = await self.get_policies()
        retrieval_id = f"retrieval_{uuid.uuid4().hex[:8]}"
        return {
            "retrieval_id": retrieval_id,
            "policies": [_policy_to_mcp(p) for p in policies],
            "lessons": [
                {
                    "lesson_id": r.lesson.lesson_id,
                    "score": round(r.score, 4),
                    "lesson": r.lesson.fix,
                    "telemetry_id": r.telemetry_id,
                }
                for r in results
            ],
        }

    async def report_outcome(
        self,
        lesson_id: str,
        used: bool,
        accepted: bool,
        improved: bool,
        retrieval_id: str | None = None,
        run_id: str | None = None,
    ) -> dict:
        result = await self.telemetry.record_outcome(
            retrieval_id,
            lesson_id,
            run_id,
            used,
            accepted,
            improved,
        )
        lesson = await self.storage.get_lesson(lesson_id)
        confidence = lesson.confidence.model_dump(mode="json") if lesson else {}
        return {
            "telemetry_id": result.get("telemetry_id"),
            "lesson_id": lesson_id,
            "confidence": confidence,
        }

    async def add_policy_rule(self, rule: str, namespace: str = "global", priority: int = 100) -> dict:
        policy_id = f"policy_{uuid.uuid4().hex[:8]}"
        policy = PolicyVersion(
            policy_id=policy_id,
            version="v1",
            rules=[rule[:600]],
            priority=priority,
        )
        await self.create_policy(policy)
        return {"id": policy_id, "rule": rule[:600], "namespace": namespace, "priority": priority}

    async def add_mcp_skill(
        self,
        name: str,
        description: str,
        steps: list[str],
        workflow: str | None = None,
        tools: list[str] | None = None,
        namespace: str = "global",
        version: str = "0.1.0",
        metadata: dict | None = None,
    ) -> dict:
        skill = Skill(
            skill_id=f"skill_{uuid.uuid4().hex[:8]}",
            name=name[:120],
            version=version[:40],
            description=description[:1000],
            steps=[step[:500] for step in steps],
            tool_bindings=[tool[:120] for tool in (tools or [])],
            metadata={"namespace": namespace, "workflow": workflow, **(metadata or {})},
        )
        skill_id = await self.create_skill(skill)
        return {
            "id": skill_id,
            "name": skill.name,
            "version": skill.version,
            "namespace": namespace,
            "workflow": workflow,
        }

    async def search_mcp_skills(
        self,
        query: str,
        workflow: str | None = None,
        namespace: str = "global",
        top_k: int = 5,
    ) -> list[dict]:
        skills = await self.search_skills(query)
        matches = []
        for skill in skills:
            skill_ns = skill.metadata.get("namespace", "global")
            if skill_ns != "global" and skill_ns != namespace:
                continue
            if workflow and skill.metadata.get("workflow") and skill.metadata.get("workflow") != workflow:
                continue
            matches.append(
                {
                    "skill_id": skill.skill_id,
                    "name": skill.name,
                    "version": skill.version,
                    "workflow": skill.metadata.get("workflow"),
                    "description": skill.description,
                    "score": 0.5,
                }
            )
        return matches[:top_k]

    async def get_mcp_skill(self, skill_id: str) -> dict | None:
        skill = await self.skills.get(skill_id)
        if not skill:
            return None
        return skill.model_dump(mode="json")

    async def list_pending(self) -> list:
        pending = await self.promotion.list_pending()
        return [p.model_dump(mode="json") for p in pending]

    # --- Memory ---
    async def retrieve(self, request: MemorySearchRequest) -> list[MemorySearchResult]:
        return await self.retriever.retrieve(request)

    async def store_lesson(self, lesson: Lesson) -> str:
        return await self.storage.save_lesson(lesson)

    async def get_lesson(self, lesson_id: str) -> Lesson | None:
        return await self.storage.get_lesson(lesson_id)

    async def get_provenance(self, lesson_id: str) -> dict | None:
        lesson = await self.storage.get_lesson(lesson_id)
        if not lesson:
            return None
        return lesson.provenance.model_dump(mode="json")

    async def get_graph(self, lesson_id: str) -> dict | None:
        lesson = await self.storage.get_lesson(lesson_id)
        if not lesson:
            return None
        return graph_to_dict(lesson)

    async def prune_memory(self) -> dict:
        return await self.pruner.prune()

    # --- Telemetry ---
    async def record_lesson_outcome(
        self,
        lesson_id: str,
        telemetry_id: str | None = None,
        run_id: str | None = None,
        used: bool = False,
        accepted: bool = False,
        improved: bool | None = None,
    ) -> dict:
        return await self.telemetry.record_outcome(
            telemetry_id, lesson_id, run_id, used, accepted, improved
        )

    # --- Policies ---
    async def get_policies(self) -> list[PolicyVersion]:
        return await self.policies.get_active()

    async def create_policy(self, policy: PolicyVersion) -> str:
        old = await self.policies.get_active_version_string()
        result = await self.policies.create_policy(policy)
        if old != "none":
            await self.policies.flag_lessons_for_revalidation(old)
        return result

    async def list_policy_versions(self, policy_id: str) -> list[PolicyVersion]:
        return await self.policies.list_versions(policy_id)

    # --- Recommendations & analytics ---
    async def get_recommendations(self, **kwargs) -> list[dict]:
        return await self.recommendations.get_recommendations(**kwargs)

    async def detect_patterns(self) -> list[dict]:
        return await self.patterns.detect_patterns()

    async def evaluate(self, run_id: str) -> dict:
        return await self.evaluator.evaluate_run(run_id)

    async def agent_score(self, agent_id: str | None = None) -> dict:
        return await self.evaluator.agent_score(agent_id)

    async def get_analytics(self) -> dict:
        return await self.analytics.get_analytics()

    async def workflow_health(self, workflow_id: str) -> dict:
        return await self.analytics.workflow_health(workflow_id)

    async def top_failures(self) -> list[dict]:
        return await self.analytics.top_failures()

    # --- Experiments & rollback ---
    async def start_experiment(self, **kwargs):
        return await self.experiments.start(**kwargs)

    async def end_experiment(self, experiment_id: str):
        return await self.experiments.conclude(experiment_id)

    async def experiment_results(self, experiment_id: str):
        return await self.experiments.get_results(experiment_id)

    async def rollback_resource(self, resource_type: str, resource_id: str, target_version: str) -> dict:
        return await self.rollback.rollback(resource_type, resource_id, target_version)

    async def list_versions(self, resource_type: str, resource_id: str):
        return await self.rollback.list_versions(resource_type, resource_id)

    # --- Skills ---
    async def create_skill(self, skill: Skill) -> str:
        return await self.skills.create(skill)

    async def search_skills(self, query: str) -> list[Skill]:
        return await self.skills.search(query)

    # --- Optimizers ---
    async def prompt_suggestions(self, agent_id: str, step: str, current_prompt: str) -> dict:
        return await self.prompt_optimizer.suggest(agent_id, step, current_prompt)

    async def workflow_suggestions(self, workflow_id: str) -> dict:
        return await self.workflow_optimizer.analyze(workflow_id)


def _parse_namespace_string(namespace: str) -> tuple[str | None, str | None]:
    if namespace and ":" in namespace:
        level, ns_id = namespace.split(":", 1)
        return level, ns_id
    if namespace == "global":
        return "global", None
    return None, namespace


def _namespace_string(level: str | None, ns_id: str | None) -> str:
    if level and ns_id:
        return f"{level}:{ns_id}"
    return level or ns_id or "global"


def _stage_from_events(events: list[dict]) -> StageMetadata:
    if not events:
        return StageMetadata()
    stage_data = events[0].get("stage", {})
    return StageMetadata(**stage_data)


def _policy_to_mcp(policy: PolicyVersion) -> dict:
    return {
        "id": policy.policy_id,
        "version": policy.version,
        "rule": policy.rules[0] if policy.rules else "",
        "priority": policy.priority,
        "namespace": "global",
    }
