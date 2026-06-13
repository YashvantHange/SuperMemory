"""UALL Python SDK — local and remote modes."""

import os
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx

from storage.adapters.file import get_storage
from uall.service import UALLService
from uall_core.schemas.events import RunEnd, RunStart, StageMetadata
from uall_core.schemas.lesson import MemorySearchRequest


class RunContext:
    def __init__(self, client: "UALLClient", run_id: str, workflow_id: str, stage: StageMetadata):
        self.client = client
        self.run_id = run_id
        self.workflow_id = workflow_id
        self.stage = stage
        self._lessons_used: list[str] = []

    def record_failure(self, snippet: str, tags: list[str] | None = None, **stage_kwargs) -> dict:
        stage = self._merge_stage(stage_kwargs)
        return self.client._record_failure(self.run_id, snippet, stage, tags)

    def record_correction(
        self, before: str, after: str, intent: str, **stage_kwargs
    ) -> dict:
        stage = self._merge_stage(stage_kwargs)
        return self.client._record_correction(self.run_id, before, after, intent, stage)

    def retrieve(self, query: str = "", step: str | None = None, max_tokens: int = 800) -> list[dict]:
        stage = StageMetadata(
            workflow=self.workflow_id,
            step=step or self.stage.step,
            agent=self.stage.agent,
            namespace=self.stage.namespace,
            namespace_id=self.stage.namespace_id,
        )
        results = self.client.retrieve(
            query=query or f"{self.workflow_id} {step or self.stage.step}",
            workflow=self.workflow_id,
            step=step or self.stage.step,
            namespace=self.stage.namespace,
            namespace_id=self.stage.namespace_id,
            max_tokens=max_tokens,
        )
        for r in results:
            lid = r.get("lesson", {}).get("lesson_id")
            if lid:
                self._lessons_used.append(lid)
        return results

    def report_lesson_outcome(
        self,
        lesson_id: str,
        *,
        used: bool = True,
        accepted: bool = False,
        improved: bool | None = None,
        telemetry_id: str | None = None,
    ) -> dict:
        return self.client.record_lesson_outcome(
            lesson_id,
            telemetry_id=telemetry_id,
            run_id=self.run_id,
            used=used,
            accepted=accepted,
            improved=improved,
        )

    def _merge_stage(self, kwargs: dict) -> StageMetadata:
        data = self.stage.model_dump()
        data.update({k: v for k, v in kwargs.items() if v is not None})
        return StageMetadata(**data)

    def end(self, success: bool, metrics: dict | None = None) -> dict:
        return self.client._end_run(self.run_id, success, self._lessons_used, metrics)


class UALLClient:
    """SDK supporting local (in-process) and remote (HTTP) modes."""

    def __init__(
        self,
        storage: str = "file",
        data_dir: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        self.base_url = base_url
        self.api_key = api_key or os.environ.get("UALL_API_KEY", "dev-key-change-me")
        self._service: UALLService | None = None
        if not base_url:
            os.environ.setdefault("UALL_STORAGE_BACKEND", storage)
            if data_dir:
                os.environ["UALL_DATA_DIR"] = data_dir
            self._storage = get_storage(storage, data_dir)
            self._service = UALLService(self._storage)
            self._initialized = False

    async def _ensure_init(self):
        if self._service and not self._initialized:
            await self._service.init()
            self._initialized = True

    def _sync_init(self):
        import asyncio

        if self._service and not getattr(self, "_initialized", False):
            asyncio.get_event_loop().run_until_complete(self._ensure_init())
            self._initialized = True

    @contextmanager
    def run(
        self,
        workflow_id: str,
        step: str | None = None,
        agents: list[str] | None = None,
        namespace: str | None = None,
    ):
        import asyncio

        run_id = f"run_{uuid.uuid4().hex[:8]}"
        ns_level, ns_id = ("project", "default")
        if namespace and ":" in namespace:
            ns_level, ns_id = namespace.split(":", 1)
        stage = StageMetadata(
            workflow=workflow_id,
            step=step,
            namespace=ns_level,
            namespace_id=ns_id,
        )
        start = RunStart(
            run_id=run_id,
            workflow_id=workflow_id,
            agents=agents or [],
            stage=stage,
        )
        if self._service:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._ensure_init())
                loop.run_until_complete(self._service.start_run(start))
            finally:
                loop.close()
        else:
            self._http_post("/runs/start", start.model_dump(mode="json"))

        ctx = RunContext(self, run_id, workflow_id, stage)
        try:
            yield ctx
        finally:
            pass

    def retrieve(self, **kwargs) -> list[dict]:
        import asyncio

        req = MemorySearchRequest(
            query=kwargs.get("query", ""),
            workflow=kwargs.get("workflow"),
            step=kwargs.get("step"),
            namespace=kwargs.get("namespace"),
            namespace_id=kwargs.get("namespace_id"),
            max_tokens=kwargs.get("max_tokens", 800),
            top_k=kwargs.get("top_k", 5),
        )
        if self._service:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._ensure_init())
                results = loop.run_until_complete(self._service.retrieve(req))
                return [
                    {
                        "lesson": r.lesson.model_dump(mode="json"),
                        "score": r.score,
                        "telemetry_id": r.telemetry_id,
                    }
                    for r in results
                ]
            finally:
                loop.close()
        return self._http_post("/memory/search", req.model_dump(mode="json"))

    def get_policies(self) -> list[dict]:
        import asyncio

        if self._service:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._ensure_init())
                policies = loop.run_until_complete(self._service.get_policies())
                return [p.model_dump(mode="json") for p in policies]
            finally:
                loop.close()
        return self._http_get("/policies")

    def get_recommendations(self, **kwargs) -> list[dict]:
        import asyncio

        if self._service:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._ensure_init())
                return loop.run_until_complete(self._service.get_recommendations(**kwargs))
            finally:
                loop.close()
        return self._http_post("/recommendations", kwargs)

    def record_lesson_outcome(
        self,
        lesson_id: str,
        telemetry_id: str | None = None,
        run_id: str | None = None,
        *,
        used: bool = False,
        accepted: bool = False,
        improved: bool | None = None,
    ) -> dict:
        import asyncio

        if self._service:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._ensure_init())
                return loop.run_until_complete(
                    self._service.record_lesson_outcome(
                        lesson_id, telemetry_id, run_id, used, accepted, improved
                    )
                )
            finally:
                loop.close()
        return self._http_post(
            "/telemetry/lesson-outcome",
            {
                "lesson_id": lesson_id,
                "telemetry_id": telemetry_id,
                "run_id": run_id,
                "used": used,
                "accepted": accepted,
                "improved": improved,
            },
        )

    def experiment(self, prompt_id: str, variant_b: str, split: float = 0.1) -> dict:
        import asyncio

        payload = {
            "resource_type": "prompt",
            "resource_id": prompt_id,
            "variant_a": "current",
            "variant_b": variant_b,
            "traffic_split": split,
        }
        if self._service:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._ensure_init())
                exp = loop.run_until_complete(self._service.start_experiment(**payload))
                return exp.model_dump(mode="json")
            finally:
                loop.close()
        return self._http_post("/experiments/start", payload)

    def _record_failure(self, run_id, snippet, stage, tags) -> dict:
        import asyncio
        from uall_core.schemas.events import Event, EventType

        event = Event(
            event_id=f"failure_{uuid.uuid4().hex[:8]}",
            event_type=EventType.FAILURE,
            run_id=run_id,
            stage=stage,
            tags=tags or [],
            payload={"snippet": snippet[:500]},
        )
        if self._service:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._ensure_init())
                return loop.run_until_complete(self._service.record_event(event))
            finally:
                loop.close()
        return self._http_post("/runs/event", event.model_dump(mode="json"))

    def _record_correction(self, run_id, before, after, intent, stage) -> dict:
        import asyncio
        from uall_core.schemas.events import Event, EventType

        event = Event(
            event_id=f"correction_{uuid.uuid4().hex[:8]}",
            event_type=EventType.CORRECTION,
            run_id=run_id,
            stage=stage,
            payload={"before": before[:300], "after": after[:300], "intent": intent},
        )
        if self._service:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._ensure_init())
                return loop.run_until_complete(self._service.record_event(event))
            finally:
                loop.close()
        return self._http_post("/runs/event", event.model_dump(mode="json"))

    def _end_run(self, run_id, success, lessons_used, metrics) -> dict:
        import asyncio

        data = RunEnd(run_id=run_id, success=success, lessons_used=lessons_used, metrics=metrics or {})
        if self._service:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._ensure_init())
                return loop.run_until_complete(self._service.end_run(data))
            finally:
                loop.close()
        return self._http_post("/runs/end", data.model_dump(mode="json"))

    def _http_post(self, path: str, data: dict) -> Any:
        with httpx.Client(base_url=self.base_url, headers={"X-UALL-Key": self.api_key}) as c:
            r = c.post(path, json=data)
            r.raise_for_status()
            return r.json()

    def _http_get(self, path: str) -> Any:
        with httpx.Client(base_url=self.base_url, headers={"X-UALL-Key": self.api_key}) as c:
            r = c.get(path)
            r.raise_for_status()
            return r.json()
