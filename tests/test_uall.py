import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

from uall_core.schemas.events import RunStart, StageMetadata
from uall_core.schemas.lesson import CandidateLesson, MemorySearchRequest
from uall.service import UALLService
from storage.adapters.file import FileStorageAdapter


@pytest.fixture
async def svc(tmp_path):
    storage = FileStorageAdapter(tmp_path / ".uall")
    service = UALLService(storage)
    await service.init()
    return service


@pytest.mark.asyncio
async def test_run_lifecycle(svc: UALLService):
    result = await svc.start_run(
        RunStart(run_id="run_test_1", workflow_id="pdf-pipeline", agents=["planner"])
    )
    assert result["status"] == "started"


@pytest.mark.asyncio
async def test_learning_pipeline(svc: UALLService):
    candidate = CandidateLesson(
        reflection_id="",
        failure="chose OCR for searchable PDF",
        root_cause="did not inspect text layer",
        fix="Inspect PDF text layer first; use OCR only for scanned documents",
        stage=StageMetadata(workflow="pdf-pipeline", step="planner"),
        evidence_payload={"snippet": "chose OCR for searchable PDF"},
        event_ids=["failure_001"],
    )
    result = await svc.reflect_and_queue(candidate, auto_promote=True)
    assert result["status"] in ("queued", "rejected")
    if result["status"] == "queued":
        lessons = await svc.storage.list_lessons("active")
        assert len(lessons) >= 1
        lesson = lessons[0]
        assert lesson.provenance.run_id is None or lesson.provenance.reflection_id
        assert lesson.fix


@pytest.mark.asyncio
async def test_validator_rejects_no_evidence(svc: UALLService):
    candidate = CandidateLesson(
        reflection_id="",
        failure="",
        root_cause="",
        fix="",
        evidence_payload={},
        event_ids=[],
    )
    result = await svc.validate_lesson(candidate)
    assert result.action == "reject"


@pytest.mark.asyncio
async def test_retrieval_with_policies(svc: UALLService):
    candidate = CandidateLesson(
        reflection_id="",
        failure="SQL join error",
        root_cause="schema not verified",
        fix="Inspect foreign keys before generating SQL joins",
        stage=StageMetadata(workflow="sql-pipeline", step="generator"),
        evidence_payload={"snippet": "bad join"},
        event_ids=["failure_002"],
    )
    await svc.reflect_and_queue(candidate)
    results = await svc.retrieve(
        MemorySearchRequest(query="SQL joins", step="generator", workflow="sql-pipeline")
    )
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_telemetry_recalibration(svc: UALLService):
    candidate = CandidateLesson(
        reflection_id="",
        failure="routing error",
        root_cause="bad route",
        fix="Verify document type before selecting processing pipeline",
        stage=StageMetadata(workflow="pdf-pipeline", step="planner"),
        evidence_payload={"snippet": "error"},
        event_ids=["failure_003"],
    )
    await svc.reflect_and_queue(candidate)
    lessons = await svc.storage.list_lessons("active")
    if lessons:
        lid = lessons[0].lesson_id
        await svc.record_lesson_outcome(lid, used=True, accepted=True, improved=True)
        updated = await svc.get_lesson(lid)
        assert updated.freshness.usage_count >= 1


@pytest.mark.asyncio
async def test_experiment_lifecycle(svc: UALLService):
    exp = await svc.start_experiment(
        resource_type="prompt",
        resource_id="planner",
        variant_a="v1",
        variant_b="v2",
    )
    await svc.experiments.record_run_metrics(exp.experiment_id, "b", {"success": True})
    concluded = await svc.end_experiment(exp.experiment_id)
    assert concluded.status in ("running", "concluded", "rolled_back")


@pytest.mark.asyncio
async def test_rollback(svc: UALLService):
    await svc.rollback.save_version("prompt", "planner", "v1", {"text": "original"})
    await svc.rollback.save_version("prompt", "planner", "v2", {"text": "updated"}, promoted=True)
    result = await svc.rollback_resource("prompt", "planner", "v1")
    assert result["rolled_back_to"] == "v1"


@pytest.mark.asyncio
async def test_pruning(svc: UALLService):
    result = await svc.prune_memory()
    assert "merged" in result


@pytest.mark.asyncio
async def test_analytics(svc: UALLService):
    analytics = await svc.get_analytics()
    assert "total_runs" in analytics


@pytest.mark.asyncio
async def test_sqlite_adapter(tmp_path):
    from storage.adapters.sqlite_chroma import SQLiteStorageAdapter

    storage = SQLiteStorageAdapter(tmp_path / ".uall")
    await storage.init()
    service = UALLService(storage)
    await service.init()
    await service.start_run(RunStart(run_id="run_sqlite", workflow_id="test"))
    runs = await storage.list_runs()
    assert len(runs) >= 1


@pytest.mark.asyncio
async def test_postgres_adapter(tmp_path):
    from storage.adapters.postgres_qdrant_redis import PostgresStorageAdapter

    storage = PostgresStorageAdapter(str(tmp_path / ".uall"))
    await storage.init()
    service = UALLService(storage)
    await service.init()
    await service.start_run(RunStart(run_id="run_pg", workflow_id="test"))
    runs = await storage.list_runs()
    assert len(runs) >= 1
