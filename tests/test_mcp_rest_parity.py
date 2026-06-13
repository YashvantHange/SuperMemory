"""
MCP vs REST API parity tests — same operations, both interfaces.
"""

import json
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packages"))

from uall_mcp.handlers import handle_tool, reset_service
from uall_server.main import app, API_KEY

HEADERS = {"X-UALL-Key": API_KEY}


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    reset_service()
    dd = str(tmp_path / ".supermemory")
    monkeypatch.setenv("UALL_DATA_DIR", dd)
    monkeypatch.setenv("SUPERMEMORY_STORAGE_PATH", dd)
    monkeypatch.setenv("UALL_STORAGE_BACKEND", "file")
    return dd


@pytest.fixture
async def api_client(data_dir, monkeypatch):
    monkeypatch.setenv("UALL_DATA_DIR", data_dir)
    # Re-init service with test data dir
    from uall_server import main as srv
    from storage.adapters.file import get_storage
    from uall.service import UALLService
    storage = get_storage(data_dir=data_dir)
    srv.service = UALLService(storage)
    await srv.service.init()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_parity_run_lifecycle(data_dir, api_client):
    # MCP
    mcp_start = json.loads(await handle_tool(
        "learn.run.start", {"workflow_id": "parity-wf", "step": "planner"}, data_dir=data_dir
    ))
    mcp_run_id = mcp_start["run_id"]

    # REST
    rest_start = (await api_client.post("/runs/start", headers=HEADERS, json={
        "run_id": "rest_run_001", "workflow_id": "parity-wf", "agents": [],
        "stage": {"workflow": "parity-wf", "step": "planner"},
    })).json()
    assert rest_start["status"] == "started"

    # MCP event
    mcp_ev = json.loads(await handle_tool(
        "learn.run.event",
        {"run_id": mcp_run_id, "event_type": "failure", "snippet": "parity test"},
        data_dir=data_dir,
    ))
    assert mcp_ev["recorded"]

    # REST event
    rest_ev = (await api_client.post("/runs/event", headers=HEADERS, json={
        "event_id": "failure_parity", "event_type": "failure", "run_id": "rest_run_001",
        "stage": {}, "payload": {"snippet": "parity test"},
    })).json()
    assert rest_ev["recorded"]

    # MCP end
    mcp_end = json.loads(await handle_tool(
        "learn.run.end", {"run_id": mcp_run_id, "success": False}, data_dir=data_dir
    ))
    assert mcp_end["success"] is False

    # REST end
    rest_end = (await api_client.post("/runs/end", headers=HEADERS, json={
        "run_id": "rest_run_001", "success": False, "lessons_used": [],
    })).json()
    assert rest_end["success"] is False


@pytest.mark.asyncio
async def test_parity_reflect_and_retrieve(data_dir, api_client):
    failure = json.loads(await handle_tool(
        "record_failure",
        {"summary": "join error", "workflow": "sql-pipeline", "step": "generator"},
        data_dir=data_dir,
    ))
    mcp_ref = json.loads(await handle_tool(
        "learn.reflect",
        {
            "event_ids": [failure["id"]],
            "suggestion": "Inspect foreign keys before generating SQL joins",
            "auto_promote": True,
        },
        data_dir=data_dir,
    ))
    assert mcp_ref["status"] in ("queued", "rejected")

    # REST reflect
    rest_ref = (await api_client.post("/reflection", headers=HEADERS, json={
        "candidate": {
            "reflection_id": "", "failure": "join error",
            "root_cause": "schema", "fix": "Verify schema before SQL generation",
            "evidence_payload": {"snippet": "err"}, "event_ids": ["f1"],
        },
    })).json()
    assert rest_ref["status"] in ("queued", "rejected")

    # MCP retrieve
    mcp_result = json.loads(await handle_tool(
        "learn.retrieve", {"query": "SQL joins"}, data_dir=data_dir
    ))
    mcp_lessons = mcp_result.get("lessons", [])

    # REST retrieve
    rest_lessons = (await api_client.post("/memory/search", headers=HEADERS, json={
        "query": "SQL joins", "top_k": 5,
    })).json()

    assert isinstance(mcp_lessons, list)
    assert isinstance(rest_lessons, list)
    assert len(mcp_lessons) >= 1
    assert len(rest_lessons) >= 1


@pytest.mark.asyncio
async def test_parity_policies(data_dir, api_client):
    mcp_pol = json.loads(await handle_tool("learn.policies", {}, data_dir=data_dir))
    rest_pol = (await api_client.get("/policies", headers=HEADERS)).json()
    assert len(mcp_pol) >= 1
    assert len(rest_pol) >= 1
    assert mcp_pol[0]["policy_id"] == rest_pol[0]["policy_id"]


@pytest.mark.asyncio
async def test_parity_analytics(data_dir, api_client):
    await handle_tool("learn.run.start", {"workflow_id": "a"}, data_dir=data_dir)
    mcp_an = json.loads(await handle_tool("learn.analytics", {}, data_dir=data_dir))
    rest_an = (await api_client.get("/analytics", headers=HEADERS)).json()
    assert mcp_an["total_runs"] == rest_an["total_runs"]


@pytest.mark.asyncio
async def test_parity_validate(data_dir, api_client):
    args = {
        "failure": "routing error",
        "root_cause": "no check",
        "fix": "Inspect PDF text layer first before selecting OCR tool",
        "event_ids": ["f1"],
    }
    mcp_v = json.loads(await handle_tool("learn.validate", args, data_dir=data_dir))
    rest_v = (await api_client.post("/memory/validate", headers=HEADERS, json={
        "candidate": {
            "reflection_id": "", **args, "evidence_payload": args,
        },
    })).json()
    assert mcp_v["action"] == rest_v["action"]


@pytest.mark.asyncio
async def test_parity_experiment(data_dir, api_client):
    mcp_exp = json.loads(await handle_tool(
        "learn.experiment", {"resource_id": "planner", "variant_b": "v2"}, data_dir=data_dir
    ))
    rest_exp = (await api_client.post("/experiments/start", headers=HEADERS, json={
        "resource_type": "prompt", "resource_id": "planner",
        "variant_a": "current", "variant_b": "v2",
    })).json()
    assert mcp_exp["resource_id"] == rest_exp["resource_id"]
    assert mcp_exp["status"] == rest_exp["status"]


@pytest.mark.asyncio
async def test_parity_feedback(data_dir, api_client):
    mcp_fb = json.loads(await handle_tool(
        "learn.feedback", {"rating": "positive", "comment": "helpful"}, data_dir=data_dir
    ))
    rest_fb = (await api_client.post("/feedback", headers=HEADERS, json={
        "rating": "positive", "comment": "helpful",
    })).json()
    assert "feedback_id" in mcp_fb
    assert "feedback_id" in rest_fb
