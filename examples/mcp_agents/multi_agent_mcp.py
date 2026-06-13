"""
Multi-agent MCP test — orchestrator + planner + worker via learn.* tools.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

from uall_mcp.client import UALLMCPClient


async def planner_worker(client: UALLMCPClient, run_id: str, workflow: str, lessons: list) -> str:
    lesson_text = " ".join(l.get("fix") or l.get("lesson", "") for l in lessons).lower()
    if "text layer" in lesson_text:
        return "text_layer"
    return "ocr"


async def main():
    tmp = tempfile.mkdtemp(prefix="uall_multi_")
    client = UALLMCPClient(data_dir=str(Path(tmp) / ".uall"))

    print("=== Multi-Agent MCP Test ===\n")

    # Orchestrator starts run
    start = await client.run_start(
        "pdf-pipeline", step="orchestrator",
        agents=["planner", "ocr", "generator"],
        namespace="team:eng",
    )
    run_id = start["run_id"]
    print(f"Orchestrator started run: {run_id}")

    improvements = await client.improvements(workflow_id="pdf-pipeline")
    print(f"Pre-run improvements: {len(improvements)}")

    # --- Run 1: Planner fails ---
    print("\n--- Run 1: Planner worker ---")
    lessons = await client.retrieve("PDF routing", workflow="pdf-pipeline", step="planner")
    decision = await planner_worker(client, run_id, "pdf-pipeline", lessons)
    print(f"Planner decision: {decision}")

    if decision == "ocr":
        await client.run_event(
            run_id, "failure", snippet="routed searchable PDF to OCR",
            workflow="pdf-pipeline", step="planner", agent="planner-agent",
        )
        await client.reflect(
            failure="routed searchable PDF to OCR",
            fix="Inspect PDF text layer first",
            workflow="pdf-pipeline", step="planner",
            run_id=run_id,
        )

    await client.run_end(run_id, success=False)

    # --- Run 2: Planner succeeds with lessons ---
    print("\n--- Run 2: Planner worker (with lessons) ---")
    start2 = await client.run_start("pdf-pipeline", step="planner", namespace="team:eng")
    run_id2 = start2["run_id"]
    lessons2 = await client.retrieve("PDF routing", workflow="pdf-pipeline", step="planner")
    decision2 = await planner_worker(client, run_id2, "pdf-pipeline", lessons2)
    print(f"Planner decision: {decision2}")

    lessons_used = []
    if lessons2 and decision2 == "text_layer":
        lessons_used.append(lessons2[0]["lesson_id"])
        await client.telemetry(
            lessons2[0]["lesson_id"],
            run_id=run_id2, used=True, accepted=True, improved=True,
        )

    await client.run_end(run_id2, success=decision2 == "text_layer", lessons_used=lessons_used)

    analytics = await client.analytics()
    print(f"\nFinal analytics: {analytics}")
    assert decision == "ocr", "Run 1 should choose OCR without lessons"
    assert decision2 == "text_layer", "Run 2 should choose text_layer with lessons"
    print("\n=== Multi-agent MCP test PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
