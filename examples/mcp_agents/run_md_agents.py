"""
Markdown agent runner — parses .md agent definitions and executes via UALL MCP.

Simulates how Cursor/Claude agents defined in markdown would call learn.* tools.
"""

import asyncio
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

from uall_mcp.client import UALLMCPClient


def parse_md_agent(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    role = re.search(r"\*\*Role:\*\*\s*(.+)", text)
    workflow = re.search(r"\*\*Workflow:\*\*\s*`?([^`\n]+)`?", text)
    step = re.search(r"\*\*Step:\*\*\s*`?([^`\n]+)`?", text)
    namespace = re.search(r"\*\*Namespace:\*\*\s*`?([^`\n]+)`?", text)
    tools = re.findall(r"`(learn\.[a-z.]+)`", text)
    return {
        "name": path.stem,
        "role": role.group(1).strip() if role else path.stem,
        "workflow": workflow.group(1).strip() if workflow else "default",
        "step": step.group(1).strip() if step else None,
        "namespace": namespace.group(1).strip() if namespace else "team:default",
        "tools": list(dict.fromkeys(tools)),
        "path": str(path),
    }


async def run_planner_agent(client: UALLMCPClient, agent: dict, searchable: bool) -> dict:
    """Execute planner.md agent logic via MCP."""
    start = await client.run_start(
        agent["workflow"],
        step=agent["step"] or "planner",
        agent=f"{agent['name']}-agent",
        namespace=agent["namespace"],
    )
    run_id = start["run_id"]

    policies = await client.policies()
    lessons = await client.retrieve(
        "PDF routing",
        workflow=agent["workflow"],
        step=agent["step"] or "planner",
        namespace=agent["namespace"],
    )

    lesson_text = " ".join(l.get("fix") or l.get("lesson", "") for l in lessons).lower()
    if "text layer" in lesson_text or "inspect" in lesson_text:
        decision = "text_layer" if searchable else "ocr"
    else:
        decision = "ocr"

    lessons_used = []
    if searchable and decision == "ocr":
        await client.run_event(
            run_id, "failure",
            snippet="chose OCR for searchable PDF",
            workflow=agent["workflow"], step="planner",
        )
        await client.run_event(
            run_id, "correction",
            before="route to OCR", after="inspect text layer first",
            intent="searchable PDFs should use text layer",
            workflow=agent["workflow"], step="planner",
        )
        await client.reflect(
            failure="chose OCR for searchable PDF",
            fix="Inspect PDF text layer first; use OCR only for scanned documents",
            workflow=agent["workflow"], step="planner",
            run_id=run_id,
        )
        success = False
    else:
        success = decision == ("text_layer" if searchable else "ocr")
        if lessons and success:
            lessons_used.append(lessons[0]["lesson_id"])
            await client.telemetry(
                lessons[0]["lesson_id"],
                run_id=run_id, used=True, accepted=True, improved=True,
            )

    end = await client.run_end(run_id, success=success, lessons_used=lessons_used)
    return {
        "agent": agent["name"],
        "decision": decision,
        "success": success,
        "policies_count": len(policies),
        "lessons_retrieved": len(lessons),
        "run_id": run_id,
        "evaluation": end.get("evaluation"),
    }


async def run_orchestrator_agent(client: UALLMCPClient, agent: dict, planner_result: dict) -> dict:
    """Execute orchestrator.md — aggregate and check analytics."""
    improvements = await client.improvements(workflow_id=agent["workflow"])
    analytics = await client.analytics()
    return {
        "agent": agent["name"],
        "improvements": len(improvements),
        "analytics": analytics,
        "planner_success": planner_result["success"],
    }


async def main():
    agents_dir = Path(__file__).parent / "agents"
    tmp = tempfile.mkdtemp(prefix="uall_mcp_agents_")
    client = UALLMCPClient(data_dir=str(Path(tmp) / ".uall"))

    planner_md = parse_md_agent(agents_dir / "planner.md")
    orch_md = parse_md_agent(agents_dir / "orchestrator.md")
    ocr_md = parse_md_agent(agents_dir / "ocr_worker.md")

    print("=== Markdown Agent MCP Test ===\n")
    print(f"Loaded agents: {planner_md['name']}, {orch_md['name']}, {ocr_md['name']}")
    print(f"Planner tools from .md: {planner_md['tools']}\n")

    # Run 1: failure (no prior lessons)
    print("Run 1 (searchable PDF, no lessons yet):")
    r1 = await run_planner_agent(client, planner_md, searchable=True)
    print(f"  decision={r1['decision']}, success={r1['success']}")

    # Run 2: should learn and improve
    print("\nRun 2 (searchable PDF, with learned lessons):")
    r2 = await run_planner_agent(client, planner_md, searchable=True)
    print(f"  decision={r2['decision']}, success={r2['success']}, lessons={r2['lessons_retrieved']}")

    # Orchestrator
    print("\nOrchestrator:")
    orch = await run_orchestrator_agent(client, orch_md, r2)
    print(f"  improvements={orch['improvements']}, runs={orch['analytics']['total_runs']}")

    assert r1["success"] is False, "Run 1 should fail without lessons"
    assert r2["success"] is True, "Run 2 should succeed with learned lessons"
    print("\n=== Markdown agent MCP test PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
