"""
Skill-guided MCP test — follows uall-agent-learning skill checklist via MCP tools.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

from uall_mcp.client import UALLMCPClient

SKILL_PATH = ROOT / ".cursor" / "skills" / "uall-agent-learning" / "SKILL.md"

CHECKLIST = [
    "learn.run.start",
    "learn.retrieve",
    "learn.policies",
    "learn.run.event",
    "learn.telemetry",
    "learn.run.end",
]


async def main():
    if not SKILL_PATH.exists():
        print(f"Skill not found: {SKILL_PATH}")
        sys.exit(1)

    skill_text = SKILL_PATH.read_text(encoding="utf-8")
    print("=== Skill-Guided MCP Test ===\n")
    print(f"Skill: {SKILL_PATH.name}")
    print(f"Skill size: {len(skill_text)} chars\n")

    tmp = tempfile.mkdtemp(prefix="uall_skill_")
    client = UALLMCPClient(data_dir=str(Path(tmp) / ".uall"))

    completed = []

    # Step 1: Start run
    start = await client.run_start("pdf-pipeline", step="planner", namespace="team:eng")
    run_id = start["run_id"]
    completed.append("learn.run.start")
    print(f"[OK] learn.run.start -> {run_id}")

    # Step 2: Retrieve
    lessons = await client.retrieve("PDF routing", step="planner", workflow="pdf-pipeline")
    completed.append("learn.retrieve")
    print(f"[OK] learn.retrieve -> {len(lessons)} lessons")

    # Step 3: Policies
    policies = await client.policies()
    completed.append("learn.policies")
    print(f"[OK] learn.policies -> {len(policies)} policies")

    # Step 4: Record failure (selective capture per skill)
    await client.run_event(
        run_id, "failure",
        snippet="chose OCR for searchable PDF",
        workflow="pdf-pipeline", step="planner",
    )
    completed.append("learn.run.event")
    print("[OK] learn.run.event -> failure recorded")

    # Reflect + promote (skill: closed loop)
    await client.reflect(
        failure="chose OCR for searchable PDF",
        fix="Inspect PDF text layer first",
        workflow="pdf-pipeline", step="planner",
    )
    print("[OK] learn.reflect -> lesson queued")

    # Step 5: Telemetry on second retrieval
    lessons2 = await client.retrieve("PDF routing", step="planner", workflow="pdf-pipeline")
    if lessons2:
        await client.telemetry(
            lessons2[0]["lesson_id"],
            run_id=run_id, used=True, accepted=True, improved=True,
        )
        completed.append("learn.telemetry")
        print(f"[OK] learn.telemetry -> {lessons2[0]['lesson_id']}")

    # Step 6: End run
    lessons_used = [l["lesson_id"] for l in lessons2[:1]]
    await client.run_end(run_id, success=True, lessons_used=lessons_used)
    completed.append("learn.run.end")
    print("[OK] learn.run.end -> run closed")

    # Verify skill checklist
    for tool in CHECKLIST:
        assert tool in completed, f"Skill checklist missing: {tool}"

    # Verify skill mentions our tools
    for tool in ["learn.retrieve", "learn.reflect", "learn.telemetry"]:
        assert tool in skill_text, f"Skill should document {tool}"

    analytics = await client.analytics()
    print(f"\nAnalytics: {analytics}")
    print("\n=== Skill-guided MCP test PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
