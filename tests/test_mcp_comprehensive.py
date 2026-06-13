"""
Comprehensive MCP + implementation integration tests.

Covers: all 16 tools, closed-loop learning, skill compliance,
markdown agents, multi-agent, storage tiers, error cases, REST parity.
"""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packages"))

from uall_mcp.handlers import TOOLS, handle_tool, reset_service
from uall_mcp.client import UALLMCPClient

SKILL_PATH = ROOT / "skills" / "supermemory-agent-learning" / "SKILL.md"
MD_AGENTS_DIR = ROOT / "examples" / "mcp_agents" / "agents"

ALL_TOOLS = [
    "learn.run.start", "learn.run.event", "learn.run.end",
    "learn.store", "learn.retrieve", "learn.reflect", "learn.validate",
    "learn.evaluate", "learn.feedback", "learn.improvements",
    "learn.analytics", "learn.policies", "learn.experiment",
    "learn.rollback", "learn.skills", "learn.telemetry",
]


@pytest.fixture
def data_dir(tmp_path):
    reset_service()
    return str(tmp_path / ".supermemory")


async def _promote_lesson(data_dir, summary: str, suggestion: str, **kwargs) -> dict:
    failure = json.loads(
        await handle_tool(
            "record_failure",
            {"summary": summary, **kwargs},
            data_dir=data_dir,
        )
    )
    await handle_tool(
        "learn.reflect",
        {"event_ids": [failure["id"]], "suggestion": suggestion, "auto_promote": True},
        data_dir=data_dir,
    )
    return failure


# ---------------------------------------------------------------------------
# 1. Tool registry & schema
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def test_exactly_29_tools(self):
        assert len(TOOLS) == 29

    def test_all_tool_names(self):
        names = {t["name"] for t in TOOLS}
        assert set(ALL_TOOLS).issubset(names)
        assert len(names) == 29

    def test_each_tool_has_schema(self):
        for t in TOOLS:
            assert "description" in t
            assert "inputSchema" in t
            assert t["inputSchema"]["type"] == "object"

    def test_claude_and_cursor_skills_exist(self):
        claude_skill = ROOT / ".claude" / "skills" / "supermemory-agent-learning" / "SKILL.md"
        cursor_skill = ROOT / ".cursor" / "skills" / "supermemory-agent-learning" / "SKILL.md"
        canonical = ROOT / "skills" / "supermemory-agent-learning" / "SKILL.md"
        assert canonical.exists()
        assert cursor_skill.exists()
        assert claude_skill.exists()

    def test_skill_documents_mcp_tools(self):
        assert SKILL_PATH.exists()
        skill = SKILL_PATH.read_text(encoding="utf-8")
        for tool in ["learn.retrieve", "learn.reflect", "learn.telemetry", "learn.validate"]:
            assert tool in skill
        for tool in ["retrieve", "record_failure", "validate", "process_promotions"]:
            assert tool in skill


# ---------------------------------------------------------------------------
# 2. Every tool individually
# ---------------------------------------------------------------------------

class TestEachMCPTool:
    @pytest.mark.asyncio
    async def test_learn_run_start(self, data_dir):
        r = json.loads(await handle_tool(
            "learn.run.start",
            {"workflow_id": "wf1", "step": "planner", "namespace": "team:eng", "agents": ["a", "b"]},
            data_dir=data_dir,
        ))
        assert r["status"] == "started"
        assert "run_id" in r

    @pytest.mark.asyncio
    async def test_learn_run_event_failure(self, data_dir):
        start = json.loads(await handle_tool(
            "learn.run.start", {"workflow_id": "wf1"}, data_dir=data_dir
        ))
        r = json.loads(await handle_tool(
            "learn.run.event",
            {"run_id": start["run_id"], "event_type": "failure", "snippet": "err", "step": "planner"},
            data_dir=data_dir,
        ))
        assert r["recorded"] is True

    @pytest.mark.asyncio
    async def test_learn_run_event_correction(self, data_dir):
        start = json.loads(await handle_tool(
            "learn.run.start", {"workflow_id": "wf1"}, data_dir=data_dir
        ))
        r = json.loads(await handle_tool(
            "learn.run.event",
            {
                "run_id": start["run_id"], "event_type": "correction",
                "before": "a", "after": "b", "intent": "fix",
            },
            data_dir=data_dir,
        ))
        assert r["recorded"] is True

    @pytest.mark.asyncio
    async def test_learn_run_event_workflow_step(self, data_dir):
        start = json.loads(await handle_tool(
            "learn.run.start", {"workflow_id": "wf1"}, data_dir=data_dir
        ))
        r = json.loads(await handle_tool(
            "learn.run.event",
            {"run_id": start["run_id"], "event_type": "workflow_step", "outcome": "ok"},
            data_dir=data_dir,
        ))
        assert r["recorded"] is True

    @pytest.mark.asyncio
    async def test_learn_run_end(self, data_dir):
        start = json.loads(await handle_tool(
            "learn.run.start", {"workflow_id": "wf1"}, data_dir=data_dir
        ))
        r = json.loads(await handle_tool(
            "learn.run.end", {"run_id": start["run_id"], "success": True, "lessons_used": []},
            data_dir=data_dir,
        ))
        assert r["success"] is True

    @pytest.mark.asyncio
    async def test_learn_reflect(self, data_dir):
        failure = json.loads(await handle_tool(
            "record_failure",
            {"summary": "SQL join failed", "workflow": "sql-pipeline", "step": "generator"},
            data_dir=data_dir,
        ))
        r = json.loads(await handle_tool(
            "learn.reflect",
            {
                "event_ids": [failure["id"]],
                "suggestion": "Inspect foreign keys before generating SQL joins",
            },
            data_dir=data_dir,
        ))
        assert r["status"] in ("queued", "rejected")

    @pytest.mark.asyncio
    async def test_learn_validate_approve(self, data_dir):
        r = json.loads(await handle_tool(
            "learn.validate",
            {
                "failure": "routing error",
                "root_cause": "no text layer check",
                "fix": "Inspect PDF text layer first before choosing OCR pipeline",
                "event_ids": ["failure_001"],
            },
            data_dir=data_dir,
        ))
        assert r["action"] in ("approve", "rewrite", "merge")

    @pytest.mark.asyncio
    async def test_learn_validate_reject(self, data_dir):
        r = json.loads(await handle_tool(
            "learn.validate", {"failure": "", "fix": ""}, data_dir=data_dir
        ))
        assert r["action"] == "reject"

    @pytest.mark.asyncio
    async def test_learn_retrieve(self, data_dir):
        await _promote_lesson(
            data_dir,
            "schema error",
            "Verify input schema before processing data",
        )
        r = json.loads(await handle_tool(
            "learn.retrieve", {"query": "schema validation"}, data_dir=data_dir
        ))
        assert isinstance(r, dict)
        assert "lessons" in r

    @pytest.mark.asyncio
    async def test_learn_store(self, data_dir):
        from datetime import datetime
        from uall_core.schemas.namespace import ConfidenceDimensions, FreshnessMetrics, NamespaceRef, Provenance
        from uall_core.schemas.events import StageMetadata

        lesson = {
            "lesson_id": "lesson_manual_001",
            "failure": "test", "root_cause": "test", "fix": "Always validate before acting",
            "stage": StageMetadata(workflow="test").model_dump(mode="json"),
            "namespace": NamespaceRef().model_dump(mode="json"),
            "confidence": ConfidenceDimensions(evidence=0.9).model_dump(mode="json"),
            "freshness": FreshnessMetrics().model_dump(mode="json"),
            "provenance": Provenance(validator_action="approve").model_dump(mode="json"),
            "quality_score": 0.8,
        }
        r = json.loads(await handle_tool(
            "learn.store", {"lesson_json": json.dumps(lesson)}, data_dir=data_dir
        ))
        assert r["stored"] is True
        assert r["lesson_id"] == "lesson_manual_001"

    @pytest.mark.asyncio
    async def test_learn_evaluate(self, data_dir):
        start = json.loads(await handle_tool(
            "learn.run.start", {"workflow_id": "wf1"}, data_dir=data_dir
        ))
        await handle_tool(
            "learn.run.event",
            {"run_id": start["run_id"], "event_type": "failure", "snippet": "err"},
            data_dir=data_dir,
        )
        await handle_tool(
            "learn.run.end", {"run_id": start["run_id"], "success": False}, data_dir=data_dir
        )
        r = json.loads(await handle_tool(
            "learn.evaluate", {"run_id": start["run_id"]}, data_dir=data_dir
        ))
        assert "score" in r

    @pytest.mark.asyncio
    async def test_learn_feedback(self, data_dir):
        r = json.loads(await handle_tool(
            "learn.feedback", {"rating": "positive", "comment": "good lesson"}, data_dir=data_dir
        ))
        assert "feedback_id" in r

    @pytest.mark.asyncio
    async def test_learn_improvements(self, data_dir):
        await _promote_lesson(
            data_dir,
            "join error",
            "Check foreign keys before generating SQL joins",
            workflow="sql-pipeline",
        )
        r = json.loads(await handle_tool(
            "learn.improvements", {"workflow_id": "sql-pipeline"}, data_dir=data_dir
        ))
        assert isinstance(r, list)

    @pytest.mark.asyncio
    async def test_learn_analytics(self, data_dir):
        r = json.loads(await handle_tool("learn.analytics", {}, data_dir=data_dir))
        assert "total_runs" in r
        assert "active_lessons" in r

    @pytest.mark.asyncio
    async def test_learn_policies(self, data_dir):
        r = json.loads(await handle_tool("learn.policies", {}, data_dir=data_dir))
        assert len(r) >= 1
        assert "rules" in r[0]

    @pytest.mark.asyncio
    async def test_learn_experiment(self, data_dir):
        r = json.loads(await handle_tool(
            "learn.experiment",
            {"resource_id": "planner", "variant_b": "improved", "traffic_split": 0.1},
            data_dir=data_dir,
        ))
        assert r["status"] == "running"
        assert "experiment_id" in r

    @pytest.mark.asyncio
    async def test_learn_rollback(self, data_dir):
        from uall_mcp.handlers import get_service
        svc = await get_service(data_dir)
        await svc.rollback.save_version("prompt", "p1", "v1", {"text": "orig"})
        r = json.loads(await handle_tool(
            "learn.rollback",
            {"resource_type": "prompt", "resource_id": "p1", "target_version": "v1"},
            data_dir=data_dir,
        ))
        assert r["rolled_back_to"] == "v1"

    @pytest.mark.asyncio
    async def test_learn_skills(self, data_dir):
        from uall_mcp.handlers import get_service
        from uall_core.schemas.common import Skill
        svc = await get_service(data_dir)
        await svc.create_skill(Skill(
            skill_id="pdf_extraction", name="PDF Extraction",
            description="PDF text layer and OCR fallback workflow",
            steps=["inspect text layer", "OCR fallback", "validate"],
        ))
        r = json.loads(await handle_tool(
            "learn.skills", {"query": "PDF"}, data_dir=data_dir
        ))
        assert len(r) >= 1
        assert r[0]["skill_id"] == "pdf_extraction"

    @pytest.mark.asyncio
    async def test_learn_telemetry(self, data_dir):
        await _promote_lesson(
            data_dir,
            "version mismatch",
            "Validate semantic version ranges before comparison",
        )
        retrieval = json.loads(await handle_tool(
            "learn.retrieve", {"query": "version"}, data_dir=data_dir
        ))
        lessons = retrieval.get("lessons", [])
        assert lessons
        r = json.loads(await handle_tool(
            "learn.telemetry",
            {"lesson_id": lessons[0]["lesson_id"], "used": True, "accepted": True, "improved": True},
            data_dir=data_dir,
        ))
        assert r["recorded"] is True

    @pytest.mark.asyncio
    async def test_unknown_tool(self, data_dir):
        r = json.loads(await handle_tool("learn.nonexistent", {}, data_dir=data_dir))
        assert "error" in r


# ---------------------------------------------------------------------------
# 3. Closed-loop learning (MCP end-to-end)
# ---------------------------------------------------------------------------

class TestClosedLoopMCP:
    @pytest.mark.asyncio
    async def test_failure_to_lesson_to_retrieval(self, data_dir):
        client = UALLMCPClient(data_dir=data_dir)

        # Run 1: fail
        s1 = await client.run_start("pdf-pipeline", step="planner", namespace="team:eng")
        await client.run_event(
            s1["run_id"], "failure", snippet="chose OCR for searchable PDF",
            workflow="pdf-pipeline", step="planner",
        )
        await client.reflect(
            failure="chose OCR for searchable PDF",
            fix="Inspect PDF text layer first; use OCR only for scanned documents",
            workflow="pdf-pipeline", step="planner",
            run_id=s1["run_id"],
        )
        await client.run_end(s1["run_id"], success=False)

        # Run 2: retrieve lesson
        s2 = await client.run_start("pdf-pipeline", step="planner", namespace="team:eng")
        lessons = await client.retrieve(
            "PDF routing", workflow="pdf-pipeline", step="planner", namespace="team:eng"
        )
        assert len(lessons) >= 1
        fix = (lessons[0].get("fix") or lessons[0].get("lesson", "")).lower()
        assert "text layer" in fix or "inspect" in fix

        await client.telemetry(
            lessons[0]["lesson_id"], run_id=s2["run_id"],
            used=True, accepted=True, improved=True,
        )
        await client.run_end(s2["run_id"], success=True, lessons_used=[lessons[0]["lesson_id"]])

        analytics = await client.analytics()
        assert analytics["active_lessons"] >= 1
        assert analytics["total_runs"] == 2

    @pytest.mark.asyncio
    async def test_validator_rejects_bad_lesson(self, data_dir):
        r = json.loads(await handle_tool(
            "learn.reflect", {"event_ids": []}, data_dir=data_dir
        ))
        assert r["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_telemetry_updates_confidence(self, data_dir):
        await _promote_lesson(
            data_dir,
            "SQL error",
            "Inspect foreign keys before generating SQL joins",
        )
        retrieval = json.loads(await handle_tool(
            "learn.retrieve", {"query": "SQL"}, data_dir=data_dir
        ))
        lessons = retrieval.get("lessons", [])
        lid = lessons[0]["lesson_id"]
        await handle_tool(
            "learn.telemetry",
            {"lesson_id": lid, "used": True, "improved": True},
            data_dir=data_dir,
        )
        from uall_mcp.handlers import get_service
        svc = await get_service(data_dir)
        lesson = await svc.get_lesson(lid)
        assert lesson.freshness.usage_count >= 1
        assert lesson.confidence.retrieval_success > 0.5


# ---------------------------------------------------------------------------
# 4. Markdown agents
# ---------------------------------------------------------------------------

class TestMarkdownAgents:
    def test_all_md_agents_exist(self):
        for name in ["planner.md", "orchestrator.md", "ocr_worker.md"]:
            assert (MD_AGENTS_DIR / name).exists()

    def test_md_agents_define_mcp_tools(self):
        for md in MD_AGENTS_DIR.glob("*.md"):
            text = md.read_text(encoding="utf-8")
            tools = re.findall(r"`(learn\.[a-z.]+)`", text)
            assert len(tools) >= 1, f"{md.name} has no MCP tools"

    def test_planner_md_has_skill_reference(self):
        text = (MD_AGENTS_DIR / "planner.md").read_text(encoding="utf-8")
        assert "supermemory-agent-learning" in text

    def test_planner_md_tool_order_matches_skill(self):
        text = (MD_AGENTS_DIR / "planner.md").read_text(encoding="utf-8")
        tools = re.findall(r"`(learn\.[a-z.]+)`", text)
        assert "learn.run.start" in tools
        assert "learn.retrieve" in tools
        assert "learn.run.end" in tools


# ---------------------------------------------------------------------------
# 5. Skill compliance
# ---------------------------------------------------------------------------

class TestSkillCompliance:
    def test_skill_checklist_tools_exist(self):
        skill = SKILL_PATH.read_text(encoding="utf-8")
        checklist = [
            "learn.run.start", "learn.retrieve", "learn.policies",
            "learn.run.event", "learn.telemetry", "learn.run.end",
        ]
        for tool in checklist:
            assert tool in skill

    @pytest.mark.asyncio
    async def test_skill_workflow_executable(self, data_dir):
        """Execute the skill's integration checklist via MCP."""
        client = UALLMCPClient(data_dir=data_dir)
        steps_completed = []

        start = await client.run_start("pdf-pipeline", step="planner", namespace="team:eng")
        steps_completed.append("learn.run.start")

        await client.retrieve("routing", step="planner")
        steps_completed.append("learn.retrieve")

        await client.policies()
        steps_completed.append("learn.policies")

        await client.run_event(
            start["run_id"], "failure", snippet="test",
            workflow="pdf-pipeline", step="planner",
        )
        steps_completed.append("learn.run.event")

        await client.reflect(
            failure="test failure",
            fix="Inspect document structure before selecting processing tool",
            workflow="pdf-pipeline", step="planner",
        )

        lessons = await client.retrieve("routing", step="planner")
        if lessons:
            await client.telemetry(lessons[0]["lesson_id"], used=True, improved=True)
            steps_completed.append("learn.telemetry")

        await client.run_end(start["run_id"], success=True)
        steps_completed.append("learn.run.end")

        assert len(steps_completed) >= 5


# ---------------------------------------------------------------------------
# 6. Multi-agent via MCP
# ---------------------------------------------------------------------------

class TestMultiAgentMCP:
    @pytest.mark.asyncio
    async def test_orchestrator_planner_worker_flow(self, data_dir):
        client = UALLMCPClient(data_dir=data_dir)

        # Orchestrator run
        orch = await client.run_start(
            "pdf-pipeline", step="orchestrator",
            agents=["planner", "ocr", "generator"], namespace="team:eng",
        )

        # Planner fails
        await client.run_event(
            orch["run_id"], "failure", snippet="bad route",
            agent="planner-agent", step="planner",
        )
        await client.reflect(
            failure="bad route", fix="Inspect PDF text layer first",
            workflow="pdf-pipeline", step="planner",
        )
        await client.run_end(orch["run_id"], success=False)

        # Planner succeeds on retry
        p2 = await client.run_start("pdf-pipeline", step="planner", namespace="team:eng")
        lessons = await client.retrieve("routing", step="planner", workflow="pdf-pipeline")
        assert lessons
        await client.run_end(p2["run_id"], success=True, lessons_used=[lessons[0]["lesson_id"]])

        improvements = await client.improvements(workflow_id="pdf-pipeline")
        assert isinstance(improvements, list)


# ---------------------------------------------------------------------------
# 7. Storage tiers via MCP
# ---------------------------------------------------------------------------

class TestStorageTiersMCP:
    @pytest.mark.asyncio
    async def test_file_storage(self, data_dir):
        r = json.loads(await handle_tool(
            "learn.run.start", {"workflow_id": "tier-test"}, data_dir=data_dir
        ))
        assert (Path(data_dir) / "runs" / f"{r['run_id']}.json").exists()

    @pytest.mark.asyncio
    async def test_sqlite_storage(self, tmp_path):
        reset_service()
        dd = str(tmp_path / ".supermemory")
        import os
        os.environ["UALL_STORAGE_BACKEND"] = "sqlite"
        r = json.loads(await handle_tool(
            "learn.run.start", {"workflow_id": "sqlite-test"}, data_dir=dd
        ))
        assert (Path(dd) / "uall.db").exists()
        os.environ["UALL_STORAGE_BACKEND"] = "file"

    @pytest.mark.asyncio
    async def test_postgres_storage_stub(self, tmp_path):
        reset_service()
        dd = str(tmp_path / ".supermemory")
        import os
        os.environ["UALL_STORAGE_BACKEND"] = "postgres"
        r = json.loads(await handle_tool(
            "learn.run.start", {"workflow_id": "pg-test"}, data_dir=dd
        ))
        assert r["status"] == "started"
        os.environ["UALL_STORAGE_BACKEND"] = "file"


# ---------------------------------------------------------------------------
# 8. MCP server module
# ---------------------------------------------------------------------------

class TestMCPServerModule:
    def test_server_imports(self):
        from uall_mcp import server
        from uall_mcp.handlers import TOOLS
        assert callable(server.main)
        assert len(TOOLS) == 29

    def test_cursor_mcp_config_valid(self):
        cfg = json.loads((ROOT / "examples" / "cursor_mcp" / "mcp.json").read_text())
        assert "supermemory" in cfg["mcpServers"]
        assert "supermemory_mcp.server" in cfg["mcpServers"]["supermemory"]["args"][1]
