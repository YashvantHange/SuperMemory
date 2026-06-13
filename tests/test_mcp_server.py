from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


def _tool_data(result) -> dict:
    if getattr(result, "structuredContent", None):
        return result.structuredContent
    if getattr(result, "content", None):
        import json
        return json.loads(result.content[0].text)
    return {}


@pytest.mark.anyio
async def test_mcp_stdio_lists_and_calls_tools(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(ROOT / "packages"), str(ROOT)])
    params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "supermemory_mcp.server",
            "--storage",
            str(tmp_path / ".supermemory"),
            "--transport",
            "stdio",
        ],
        env=env,
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {tool.name for tool in tools.tools}
            assert "retrieve" in tool_names
            assert "validate" in tool_names
            assert "report_outcome" in tool_names
            assert "add_skill" in tool_names
            assert "search_skills" in tool_names
            assert "learn.retrieve" in tool_names
            assert "learn.experiment" in tool_names

            policy = await session.call_tool(
                "add_policy",
                {"rule": "Never expose secrets", "namespace": "organization:default"},
            )
            policy_data = _tool_data(policy)
            assert policy_data["rule"] == "Never expose secrets"

            failure = await session.call_tool(
                "record_failure",
                {
                    "summary": "Planner skipped schema validation before SQL generation.",
                    "workflow": "sql-pipeline",
                    "step": "planner",
                    "domain": "data",
                    "namespace": "team:analytics",
                },
            )
            failure_data = _tool_data(failure)
            reflection = await session.call_tool(
                "reflect",
                {
                    "event_ids": [failure_data["id"]],
                    "suggestion": "check schema constraints before SQL generation",
                },
            )
            reflection_data = _tool_data(reflection)
            validation = await session.call_tool(
                "validate", {"reflection_id": reflection_data["id"]}
            )
            validation_data = _tool_data(validation)
            assert validation_data["action"] == "approve"

            promotions = await session.call_tool("process_promotions", {})
            promotions_data = _tool_data(promotions)
            lesson_id = promotions_data["promoted"][0]

            retrieval = await session.call_tool(
                "retrieve",
                {
                    "query": "SQL planner should validate schema",
                    "workflow": "sql-pipeline",
                    "step": "planner",
                    "namespace": "team:analytics",
                },
            )
            retrieval_data = _tool_data(retrieval)
            assert retrieval_data["lessons"][0]["lesson_id"] == lesson_id

            outcome = await session.call_tool(
                "report_outcome",
                {
                    "lesson_id": lesson_id,
                    "retrieval_id": retrieval_data["retrieval_id"],
                    "used": True,
                    "accepted": True,
                    "improved": True,
                },
            )
            outcome_data = _tool_data(outcome)
            assert outcome_data["confidence"]["human_verified"] is True

            skill = await session.call_tool(
                "add_skill",
                {
                    "name": "PDF extraction",
                    "description": "Extract text from PDFs with a text-layer check before OCR fallback.",
                    "steps": ["Inspect text layer", "Run OCR only when needed", "Validate extracted fields"],
                    "workflow": "pdf-pipeline",
                    "tools": ["pdf_reader", "ocr"],
                    "namespace": "team:docs",
                },
            )
            skill_data = _tool_data(skill)
            skills = await session.call_tool(
                "search_skills",
                {"query": "pdf ocr fallback", "workflow": "pdf-pipeline", "namespace": "team:docs"},
            )
            skills_data = _tool_data(skills)
            assert skills_data["skills"][0]["skill_id"] == skill_data["id"]


@pytest.mark.anyio
async def test_mcp_tools_have_safety_annotations(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(ROOT / "packages"), str(ROOT)])
    params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "supermemory_mcp.server",
            "--storage",
            str(tmp_path / ".supermemory"),
            "--transport",
            "stdio",
        ],
        env=env,
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert len(tools.tools) == 29
            for tool in tools.tools:
                assert tool.annotations is not None, f"{tool.name} missing annotations"
                assert tool.annotations.readOnlyHint is not None
                assert tool.annotations.destructiveHint is not None


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_stdio_prints_help_when_run_in_interactive_terminal(monkeypatch, capsys):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys, "argv", ["supermemory-agent"])
    with pytest.raises(SystemExit) as exc:
        from supermemory_mcp.server import main

        main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "MCP client" in out
    assert "streamable-http" in out
