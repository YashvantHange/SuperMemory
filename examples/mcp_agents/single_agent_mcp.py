"""
Single-agent MCP integration test.
Uses UALLMCPClient (in-process) — same handlers as stdio MCP server.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

from uall_mcp.client import UALLMCPClient


async def main():
    tmp = tempfile.mkdtemp(prefix="uall_single_")
    client = UALLMCPClient(data_dir=str(Path(tmp) / ".uall"))

    print("=== Single Agent MCP Test ===\n")

    start = await client.run_start("sql-pipeline", step="generator", namespace="team:data")
    run_id = start["run_id"]
    print(f"Started run: {run_id}")

    lessons = await client.retrieve("SQL join errors", workflow="sql-pipeline", step="generator")
    print(f"Retrieved {len(lessons)} lessons")

    await client.run_event(
        run_id, "failure",
        snippet="incorrect join on user_id",
        workflow="sql-pipeline", step="generator",
    )

    reflection = await client.reflect(
        failure="incorrect join on user_id",
        root_cause="foreign keys not verified",
        fix="Inspect foreign keys before generating SQL joins",
        workflow="sql-pipeline", step="generator",
    )
    print(f"Reflection status: {reflection.get('status')}")

    validation = await client.call(
        "learn.validate",
        failure="incorrect join",
        fix="Inspect foreign keys before generating SQL joins",
        event_ids=["failure_test"],
    )
    print(f"Validation action: {validation.get('action')}")

    end = await client.run_end(run_id, success=False)
    analytics = await client.analytics()
    print(f"Analytics: {analytics['total_runs']} runs, {analytics['active_lessons']} lessons")
    print("\n=== Single agent MCP test PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
