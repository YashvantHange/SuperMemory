import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packages"))

from uall_mcp.handlers import TOOLS, handle_tool, reset_service
from uall_mcp.client import UALLMCPClient


@pytest.fixture
def data_dir(tmp_path):
    reset_service()
    return str(tmp_path / ".supermemory")


@pytest.mark.asyncio
async def test_all_tools_registered():
    names = {t["name"] for t in TOOLS}
    github = {
        "retrieve", "record_event", "record_failure", "record_correction",
        "reflect", "validate", "process_promotions", "report_outcome",
        "get_policies", "add_policy", "add_skill", "search_skills", "get_skill",
    }
    learn = {
        "learn.run.start", "learn.run.event", "learn.run.end",
        "learn.store", "learn.retrieve", "learn.reflect", "learn.validate",
        "learn.evaluate", "learn.feedback", "learn.improvements",
        "learn.analytics", "learn.policies", "learn.experiment",
        "learn.rollback", "learn.skills", "learn.telemetry",
    }
    assert github.issubset(names)
    assert learn.issubset(names)
    assert len(TOOLS) == 29


@pytest.mark.asyncio
async def test_mcp_run_lifecycle(data_dir):
    start = json.loads(await handle_tool(
        "learn.run.start",
        {"workflow_id": "test-wf", "step": "planner", "namespace": "team:test"},
        data_dir=data_dir,
    ))
    assert start["status"] == "started"
    run_id = start["run_id"]

    event = json.loads(await handle_tool(
        "learn.run.event",
        {"run_id": run_id, "event_type": "failure", "snippet": "test error"},
        data_dir=data_dir,
    ))
    assert event["recorded"] is True

    end = json.loads(await handle_tool(
        "learn.run.end", {"run_id": run_id, "success": False}, data_dir=data_dir
    ))
    assert end["success"] is False


@pytest.mark.asyncio
async def test_mcp_reflect_and_retrieve(data_dir):
    failure = json.loads(await handle_tool(
        "record_failure",
        {
            "summary": "bad routing",
            "workflow": "pdf-pipeline",
            "step": "planner",
        },
        data_dir=data_dir,
    ))
    result = json.loads(await handle_tool(
        "learn.reflect",
        {
            "event_ids": [failure["id"]],
            "suggestion": "Inspect document type before selecting OCR pipeline",
        },
        data_dir=data_dir,
    ))
    assert result["status"] in ("queued", "rejected")

    retrieval = json.loads(await handle_tool(
        "learn.retrieve",
        {"query": "routing", "workflow": "pdf-pipeline", "step": "planner"},
        data_dir=data_dir,
    ))
    assert isinstance(retrieval, dict)
    assert "lessons" in retrieval


@pytest.mark.asyncio
async def test_mcp_validate_rejects_no_evidence(data_dir):
    result = json.loads(await handle_tool(
        "learn.validate",
        {"failure": "", "fix": ""},
        data_dir=data_dir,
    ))
    assert result["action"] == "reject"


@pytest.mark.asyncio
async def test_mcp_policies(data_dir):
    policies = json.loads(await handle_tool("learn.policies", {}, data_dir=data_dir))
    assert isinstance(policies, list)
    assert len(policies) >= 1


@pytest.mark.asyncio
async def test_mcp_telemetry(data_dir):
    failure = json.loads(await handle_tool(
        "record_failure",
        {"summary": "schema error", "workflow": "test"},
        data_dir=data_dir,
    ))
    await handle_tool(
        "learn.reflect",
        {
            "event_ids": [failure["id"]],
            "suggestion": "Verify schema constraints before generating output",
            "auto_promote": True,
        },
        data_dir=data_dir,
    )
    retrieval = json.loads(await handle_tool(
        "learn.retrieve", {"query": "schema"}, data_dir=data_dir
    ))
    lessons = retrieval.get("lessons", [])
    if lessons:
        tel = json.loads(await handle_tool(
            "learn.telemetry",
            {"lesson_id": lessons[0]["lesson_id"], "used": True, "improved": True},
            data_dir=data_dir,
        ))
        assert tel["recorded"] is True


@pytest.mark.asyncio
async def test_mcp_client_wrapper(data_dir):
    client = UALLMCPClient(data_dir=data_dir)
    start = await client.run_start("wf", step="s1")
    assert "run_id" in start
    analytics = await client.analytics()
    assert "total_runs" in analytics


@pytest.mark.asyncio
async def test_mcp_experiment_and_rollback(data_dir):
    exp = json.loads(await handle_tool(
        "learn.experiment",
        {"resource_id": "planner", "variant_b": "improved prompt"},
        data_dir=data_dir,
    ))
    assert "experiment_id" in exp

    svc_storage = None
    from uall_mcp.handlers import get_service
    svc = await get_service(data_dir)
    await svc.rollback.save_version("prompt", "planner", "v1", {"text": "original"})
    result = json.loads(await handle_tool(
        "learn.rollback",
        {"resource_type": "prompt", "resource_id": "planner", "target_version": "v1"},
        data_dir=data_dir,
    ))
    assert result["rolled_back_to"] == "v1"
