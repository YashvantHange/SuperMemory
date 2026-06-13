import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from uall_core.ports.storage import StoragePort
from uall_core.providers.heuristic import cosine_similarity
from uall_core.schemas.common import (
    Experiment,
    PolicyVersion,
    RetrievalTelemetryEvent,
    Skill,
    VersionRecord,
)
from uall_core.schemas.events import Event, Feedback, RunEnd, RunStart
from uall_core.schemas.graph import KnowledgeGraph
from uall_core.schemas.lesson import Lesson, MemorySearchRequest, PendingLesson
from uall_core.schemas.namespace import (
    ConfidenceDimensions,
    FreshnessMetrics,
    NamespaceRef,
    Provenance,
    TTLConfig,
)
from uall_core.schemas.events import StageMetadata

UALL_DIRS = [
    "events",
    "runs",
    "metrics",
    "feedback",
    "recommendations",
    "prompt_versions",
    "workflow_graphs",
    "experiment_results",
    "policies",
    "skills",
    "lessons",
    "pending",
    "telemetry",
    "reflections",
    "corrections",
    "semantic_memories",
    "failure_patterns",
    "cache",
    "logs",
    "uploads",
    "artifacts",
]


class FileStorageAdapter:
    """Tier 1: file-based .uall/ storage."""

    def __init__(self, base_dir: str | Path = ".uall"):
        self.base = Path(base_dir)

    async def init(self) -> None:
        self.base.mkdir(parents=True, exist_ok=True)
        for d in UALL_DIRS:
            (self.base / d).mkdir(exist_ok=True)
        config_path = self.base / "config.json"
        if not config_path.exists():
            self._write_json(
                config_path,
                {
                    "storage_backend": "file",
                    "promotion_delay_minutes": 0,
                    "created_at": datetime.utcnow().isoformat(),
                },
            )

    def _dir(self, name: str) -> Path:
        return self.base / name

    def _write_json(self, path: Path, data: dict | list) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _read_json(self, path: Path) -> dict | list | None:
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _next_id(self, directory: str, prefix: str) -> str:
        existing = list(self._dir(directory).glob(f"{prefix}_*.json"))
        nums = []
        for p in existing:
            try:
                nums.append(int(p.stem.split("_")[-1]))
            except ValueError:
                pass
        n = max(nums, default=0) + 1
        return f"{prefix}_{n:03d}"

    async def save_run_start(self, run: RunStart) -> None:
        path = self._dir("runs") / f"{run.run_id}.json"
        data = run.model_dump(mode="json")
        data["status"] = "running"
        data["started_at"] = datetime.utcnow().isoformat()
        self._write_json(path, data)

    async def save_run_end(self, run: RunEnd) -> None:
        path = self._dir("runs") / f"{run.run_id}.json"
        existing = self._read_json(path) or {"run_id": run.run_id}
        existing.update(run.model_dump(mode="json"))
        existing["status"] = "completed"
        existing["ended_at"] = datetime.utcnow().isoformat()
        self._write_json(path, existing)

    async def save_event(self, event: Event) -> None:
        event_data = event.model_dump(mode="json")
        self._write_json(self._dir("events") / f"{event.event_id}.json", event_data)
        run_path = self._dir("runs") / f"{event.run_id}.json"
        run_data = self._read_json(run_path) or {"run_id": event.run_id, "events": []}
        if "events" not in run_data:
            run_data["events"] = []
        run_data["events"].append(event_data)
        self._write_json(run_path, run_data)

    async def get_event(self, event_id: str) -> dict[str, Any] | None:
        data = self._read_json(self._dir("events") / f"{event_id}.json")
        if data:
            return data
        for run_path in self._dir("runs").glob("*.json"):
            run_data = self._read_json(run_path)
            if not run_data:
                continue
            for evt in run_data.get("events", []):
                if evt.get("event_id") == event_id:
                    return evt
        return None

    async def save_feedback(self, feedback: Feedback) -> str:
        fid = self._next_id("feedback", "feedback")
        self._write_json(self._dir("feedback") / f"{fid}.json", feedback.model_dump(mode="json"))
        return fid

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self._read_json(self._dir("runs") / f"{run_id}.json")

    async def list_runs(self) -> list[dict[str, Any]]:
        runs = []
        for p in self._dir("runs").glob("*.json"):
            data = self._read_json(p)
            if data:
                runs.append(data)
        return runs

    def _lesson_from_dict(self, data: dict) -> Lesson:
        graph = None
        if data.get("graph"):
            graph = KnowledgeGraph(**data["graph"])
        return Lesson(
            lesson_id=data["lesson_id"],
            failure=data.get("failure", ""),
            root_cause=data.get("root_cause", ""),
            fix=data.get("fix", ""),
            memory_type=data.get("memory_type", "failure"),
            stage=StageMetadata(**data.get("stage", {})),
            namespace=NamespaceRef(**data.get("namespace", {})),
            confidence=ConfidenceDimensions(**data.get("confidence", {})),
            freshness=FreshnessMetrics(**data.get("freshness", {})),
            ttl=TTLConfig(**data.get("ttl", {})),
            provenance=Provenance(**data.get("provenance", {})),
            graph=graph,
            occurrence_count=data.get("occurrence_count", 1),
            quality_score=data.get("quality_score", 0.5),
            embedding=data.get("embedding"),
            status=data.get("status", "active"),
            metadata=data.get("metadata", {}),
        )

    async def save_lesson(self, lesson: Lesson) -> str:
        path = self._dir("lessons") / f"{lesson.lesson_id}.json"
        data = lesson.model_dump(mode="json")
        self._write_json(path, data)
        if lesson.embedding:
            self._write_json(path.with_suffix(".embedding.json"), {"embedding": lesson.embedding})
        return lesson.lesson_id

    async def get_lesson(self, lesson_id: str) -> Lesson | None:
        data = self._read_json(self._dir("lessons") / f"{lesson_id}.json")
        if not data:
            return None
        emb_path = self._dir("lessons") / f"{lesson_id}.embedding.json"
        emb_data = self._read_json(emb_path)
        if emb_data:
            data["embedding"] = emb_data.get("embedding")
        return self._lesson_from_dict(data)

    async def list_lessons(self, status: str = "active") -> list[Lesson]:
        lessons = []
        for p in self._dir("lessons").glob("*.json"):
            if p.name.endswith(".embedding.json"):
                continue
            data = self._read_json(p)
            if data and (status == "all" or data.get("status", "active") == status):
                emb = self._read_json(p.with_suffix(".embedding.json"))
                if emb:
                    data["embedding"] = emb.get("embedding")
                lessons.append(self._lesson_from_dict(data))
        return lessons

    async def update_lesson(self, lesson: Lesson) -> None:
        await self.save_lesson(lesson)

    async def delete_lesson(self, lesson_id: str) -> None:
        path = self._dir("lessons") / f"{lesson_id}.json"
        if path.exists():
            path.unlink()
        emb = self._dir("lessons") / f"{lesson_id}.embedding.json"
        if emb.exists():
            emb.unlink()

    async def search_lessons(self, request: MemorySearchRequest) -> list[Lesson]:
        lessons = await self.list_lessons("active")
        now = datetime.utcnow()
        filtered = []
        for lesson in lessons:
            if lesson.ttl.expires_at and lesson.ttl.expires_at < now:
                continue
            if request.workflow and lesson.stage.workflow != request.workflow:
                if lesson.stage.workflow is not None:
                    continue
            if request.step and lesson.stage.step != request.step:
                pass  # soft filter handled in retrieval scoring
            if request.namespace and lesson.namespace.namespace_id != request.namespace:
                pass
            filtered.append(lesson)
        if not filtered:
            filtered = await self.list_lessons("active")

        # Simple vector search if embeddings exist
        from uall_core.providers.heuristic import HeuristicLLMProvider

        provider = HeuristicLLMProvider()
        query_emb = await provider.embed(request.query)
        scored = []
        for lesson in filtered:
            emb = lesson.embedding or await provider.embed(lesson.to_search_text())
            sim = cosine_similarity(query_emb, emb)
            scored.append((sim, lesson))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [l for _, l in scored[: request.top_k * 4]]

    async def save_pending(self, pending: PendingLesson) -> str:
        path = self._dir("pending") / f"{pending.pending_id}.json"
        self._write_json(path, pending.model_dump(mode="json"))
        return pending.pending_id

    async def get_pending(self, pending_id: str) -> PendingLesson | None:
        data = self._read_json(self._dir("pending") / f"{pending_id}.json")
        return PendingLesson(**data) if data else None

    async def list_pending(self, status: str = "pending") -> list[PendingLesson]:
        result = []
        for p in self._dir("pending").glob("*.json"):
            data = self._read_json(p)
            if data and (status == "all" or data.get("status") == status):
                result.append(PendingLesson(**data))
        return result

    async def update_pending(self, pending: PendingLesson) -> None:
        await self.save_pending(pending)

    async def save_policy(self, policy: PolicyVersion) -> str:
        fname = f"{policy.policy_id}_{policy.version}.json"
        self._write_json(self._dir("policies") / fname, policy.model_dump(mode="json"))
        return f"{policy.policy_id}:{policy.version}"

    async def get_active_policies(self) -> list[PolicyVersion]:
        policies: dict[str, PolicyVersion] = {}
        for p in self._dir("policies").glob("*.json"):
            data = self._read_json(p)
            if data:
                pv = PolicyVersion(**data)
                key = pv.policy_id
                if key not in policies or pv.version > policies[key].version:
                    policies[key] = pv
        return list(policies.values())

    async def list_policy_versions(self, policy_id: str) -> list[PolicyVersion]:
        versions = []
        for p in self._dir("policies").glob(f"{policy_id}_*.json"):
            data = self._read_json(p)
            if data:
                versions.append(PolicyVersion(**data))
        return sorted(versions, key=lambda x: x.version)

    async def save_skill(self, skill: Skill) -> str:
        self._write_json(self._dir("skills") / f"{skill.skill_id}.json", skill.model_dump(mode="json"))
        return skill.skill_id

    async def get_skill(self, skill_id: str) -> Skill | None:
        data = self._read_json(self._dir("skills") / f"{skill_id}.json")
        return Skill(**data) if data else None

    async def search_skills(self, query: str) -> list[Skill]:
        q = query.lower()
        skills = []
        for p in self._dir("skills").glob("*.json"):
            data = self._read_json(p)
            if data:
                s = Skill(**data)
                searchable = " ".join(
                    [s.name, s.description, " ".join(s.steps), " ".join(s.tool_bindings)]
                ).lower()
                if q in searchable or all(word in searchable for word in q.split()):
                    skills.append(s)
        return skills

    async def save_telemetry(self, event: RetrievalTelemetryEvent) -> str:
        self._write_json(
            self._dir("telemetry") / f"{event.telemetry_id}.json", event.model_dump(mode="json")
        )
        return event.telemetry_id

    async def list_telemetry(self, lesson_id: str | None = None) -> list[RetrievalTelemetryEvent]:
        events = []
        for p in self._dir("telemetry").glob("*.json"):
            data = self._read_json(p)
            if data:
                e = RetrievalTelemetryEvent(**data)
                if lesson_id is None or e.lesson_id == lesson_id:
                    events.append(e)
        return events

    async def save_experiment(self, experiment: Experiment) -> str:
        self._write_json(
            self._dir("experiment_results") / f"{experiment.experiment_id}.json",
            experiment.model_dump(mode="json"),
        )
        return experiment.experiment_id

    async def get_experiment(self, experiment_id: str) -> Experiment | None:
        data = self._read_json(self._dir("experiment_results") / f"{experiment_id}.json")
        return Experiment(**data) if data else None

    async def update_experiment(self, experiment: Experiment) -> None:
        await self.save_experiment(experiment)

    async def save_version(self, record: VersionRecord) -> str:
        vid = f"{record.resource_id}_{record.version}"
        subdir = self._dir("prompt_versions" if record.resource_type == "prompt" else "workflow_graphs")
        self._write_json(subdir / f"{vid}.json", record.model_dump(mode="json"))
        return vid

    async def list_versions(self, resource_type: str, resource_id: str) -> list[VersionRecord]:
        subdir = self._dir("prompt_versions" if resource_type == "prompt" else "workflow_graphs")
        records = []
        for p in subdir.glob(f"{resource_id}_*.json"):
            data = self._read_json(p)
            if data:
                records.append(VersionRecord(**data))
        return sorted(records, key=lambda x: x.created_at)

    async def save_reflection(self, data: dict[str, Any]) -> str:
        rid = data.get("reflection_id") or self._next_id("reflections", "reflection")
        data["reflection_id"] = rid
        self._write_json(self._dir("reflections") / f"{rid}.json", data)
        return rid

    async def get_reflection(self, reflection_id: str) -> dict[str, Any] | None:
        return self._read_json(self._dir("reflections") / f"{reflection_id}.json")

    async def save_metrics(self, name: str, data: dict[str, Any]) -> None:
        self._write_json(self._dir("metrics") / f"{name}.json", data)

    async def get_metrics(self, name: str) -> dict[str, Any] | None:
        return self._read_json(self._dir("metrics") / f"{name}.json")


def get_storage(backend: str | None = None, data_dir: str | None = None) -> StoragePort:
    backend = backend or os.environ.get("UALL_STORAGE_BACKEND", "file")
    data_dir = (
        data_dir
        or os.environ.get("SUPERMEMORY_STORAGE_PATH")
        or os.environ.get("UALL_DATA_DIR")
        or ".supermemory"
    )

    if backend == "file":
        return FileStorageAdapter(data_dir)
    if backend == "sqlite":
        from storage.adapters.sqlite_chroma import SQLiteStorageAdapter

        return SQLiteStorageAdapter(data_dir)
    if backend == "postgres":
        from storage.adapters.postgres_qdrant_redis import PostgresStorageAdapter

        return PostgresStorageAdapter()
    raise ValueError(f"Unknown storage backend: {backend}")
