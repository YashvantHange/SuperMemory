"""GitHub-compatible closed-loop tests for SuperMemory MCP core."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packages"))

from supermemory_mcp.handlers import handle_tool, reset_service


@pytest.fixture
def data_dir(tmp_path):
    reset_service()
    return str(tmp_path / ".supermemory")


@pytest.mark.asyncio
async def test_closed_loop_promotes_and_retrieves(data_dir):
    await handle_tool(
        "add_policy",
        {"rule": "Never expose secrets", "namespace": "organization:default"},
        data_dir=data_dir,
    )

    failure = json.loads(
        await handle_tool(
            "record_failure",
            {
                "summary": "Planner skipped schema validation before SQL generation.",
                "workflow": "sql-pipeline",
                "step": "planner",
                "domain": "data",
                "namespace": "team:analytics",
            },
            data_dir=data_dir,
        )
    )
    reflection = json.loads(
        await handle_tool(
            "reflect",
            {
                "event_ids": [failure["id"]],
                "suggestion": "check schema constraints before SQL generation",
            },
            data_dir=data_dir,
        )
    )
    validation = json.loads(
        await handle_tool("validate", {"reflection_id": reflection["id"]}, data_dir=data_dir)
    )
    assert validation["action"] == "approve"

    promotions = json.loads(await handle_tool("process_promotions", {}, data_dir=data_dir))
    assert len(promotions["promoted"]) == 1
    lesson_id = promotions["promoted"][0]

    retrieval = json.loads(
        await handle_tool(
            "retrieve",
            {
                "query": "SQL planner should validate schema",
                "workflow": "sql-pipeline",
                "step": "planner",
                "namespace": "team:analytics",
            },
            data_dir=data_dir,
        )
    )
    assert retrieval["policies"]
    assert retrieval["lessons"][0]["lesson_id"] == lesson_id

    outcome = json.loads(
        await handle_tool(
            "report_outcome",
            {
                "lesson_id": lesson_id,
                "retrieval_id": retrieval["retrieval_id"],
                "used": True,
                "accepted": True,
                "improved": True,
            },
            data_dir=data_dir,
        )
    )
    assert outcome["confidence"]["human_verified"] is True


@pytest.mark.asyncio
async def test_validation_rejects_unsupported_lesson(data_dir):
    result = json.loads(
        await handle_tool(
            "validate",
            {"candidate_lesson": "Always do magic.", "event_ids": []},
            data_dir=data_dir,
        )
    )
    assert result["action"] == "reject"
    assert "evidence" in result["reason"].lower()


@pytest.mark.asyncio
async def test_skill_library_searches_namespace_visible_skills(data_dir):
    skill = json.loads(
        await handle_tool(
            "add_skill",
            {
                "name": "PDF extraction",
                "description": "Extract text from PDFs with a text-layer check before OCR fallback.",
                "steps": ["Inspect text layer", "Run OCR only when needed", "Validate extracted fields"],
                "workflow": "pdf-pipeline",
                "tools": ["pdf_reader", "ocr"],
                "namespace": "team:docs",
            },
            data_dir=data_dir,
        )
    )
    skills = json.loads(
        await handle_tool(
            "search_skills",
            {"query": "pdf ocr fallback", "workflow": "pdf-pipeline", "namespace": "team:docs"},
            data_dir=data_dir,
        )
    )
    assert skills["skills"][0]["skill_id"] == skill["id"]

    fetched = json.loads(await handle_tool("get_skill", {"skill_id": skill["id"]}, data_dir=data_dir))
    assert fetched["name"] == "PDF extraction"
