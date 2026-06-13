"""SuperMemory MCP server — FastMCP with GitHub-compatible tools + MCP resources."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp.types import ToolAnnotations

_RO = ToolAnnotations(readOnlyHint=True, destructiveHint=False)
_RW = ToolAnnotations(readOnlyHint=False, destructiveHint=False)
_DX = ToolAnnotations(readOnlyHint=False, destructiveHint=True)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT / "src"))

from supermemory_mcp.handlers import handle_tool, reset_service


def build_server(storage_root: str | None = None):
    from mcp.server.fastmcp import FastMCP

    data_dir = (
        storage_root
        or os.getenv("SUPERMEMORY_STORAGE_PATH")
        or os.getenv("UALL_DATA_DIR")
        or ".supermemory"
    )
    reset_service()
    mcp = FastMCP("SuperMemory", json_response=True)

    async def _call(name: str, arguments: dict | None = None) -> dict:
        raw = await handle_tool(name, arguments or {}, data_dir=data_dir)
        return json.loads(raw)

    @mcp.tool(name="record_event", annotations=_RW)
    async def record_event(
        event_type: str,
        summary: str,
        workflow: str | None = None,
        step: str | None = None,
        tool: str | None = None,
        agent: str | None = None,
        domain: str | None = None,
        language: str | None = None,
        environment: str | None = None,
        namespace: str = "global",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record a bounded significant event. Full transcripts should not be sent here."""
        return await _call(
            "record_event",
            {
                "event_type": event_type,
                "summary": summary,
                "workflow": workflow,
                "step": step,
                "tool": tool,
                "agent": agent,
                "domain": domain,
                "language": language,
                "environment": environment,
                "namespace": namespace,
                "payload": payload,
            },
        )

    @mcp.tool(name="record_failure", annotations=_RW)
    async def record_failure(
        summary: str,
        workflow: str | None = None,
        step: str | None = None,
        tool: str | None = None,
        agent: str | None = None,
        domain: str | None = None,
        language: str | None = None,
        environment: str | None = None,
        namespace: str = "global",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record a bounded failure signal."""
        return await _call(
            "record_failure",
            {
                "summary": summary,
                "workflow": workflow,
                "step": step,
                "tool": tool,
                "agent": agent,
                "domain": domain,
                "language": language,
                "environment": environment,
                "namespace": namespace,
                "payload": payload,
            },
        )

    @mcp.tool(name="record_correction", annotations=_RW)
    async def record_correction(
        summary: str,
        workflow: str | None = None,
        step: str | None = None,
        tool: str | None = None,
        agent: str | None = None,
        domain: str | None = None,
        language: str | None = None,
        environment: str | None = None,
        namespace: str = "global",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record a bounded correction signal."""
        return await _call(
            "record_correction",
            {
                "summary": summary,
                "workflow": workflow,
                "step": step,
                "tool": tool,
                "agent": agent,
                "domain": domain,
                "language": language,
                "environment": environment,
                "namespace": namespace,
                "payload": payload,
            },
        )

    @mcp.tool(name="reflect", annotations=_RW)
    async def reflect(
        event_ids: list[str],
        suggestion: str | None = None,
        lesson_text: str | None = None,
    ) -> dict[str, Any]:
        """Create a candidate lesson from evidence events."""
        return await _call(
            "reflect",
            {"event_ids": event_ids, "suggestion": suggestion, "lesson_text": lesson_text},
        )

    @mcp.tool(name="validate", annotations=_RW)
    async def validate(
        reflection_id: str | None = None,
        candidate_lesson: str | None = None,
        event_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate a lesson candidate and enqueue approved lessons for promotion."""
        return await _call(
            "validate",
            {
                "reflection_id": reflection_id,
                "candidate_lesson": candidate_lesson,
                "event_ids": event_ids,
                "metadata": metadata,
            },
        )

    @mcp.tool(name="process_promotions", annotations=_RW)
    async def process_promotions(limit: int = 50) -> dict[str, Any]:
        """Process pending validated lessons and promote passing items."""
        return await _call("process_promotions", {"limit": limit})

    @mcp.tool(name="retrieve", annotations=_RO)
    async def retrieve(
        query: str,
        workflow: str | None = None,
        step: str | None = None,
        tool: str | None = None,
        agent: str | None = None,
        domain: str | None = None,
        language: str | None = None,
        environment: str | None = None,
        namespace: str = "global",
        top_k: int = 5,
        max_tokens: int = 800,
    ) -> dict[str, Any]:
        """Retrieve policy-first, stage-aware lessons."""
        return await _call(
            "retrieve",
            {
                "query": query,
                "workflow": workflow,
                "step": step,
                "tool": tool,
                "agent": agent,
                "domain": domain,
                "language": language,
                "environment": environment,
                "namespace": namespace,
                "top_k": top_k,
                "max_tokens": max_tokens,
            },
        )

    @mcp.tool(name="report_outcome", annotations=_RW)
    async def report_outcome(
        lesson_id: str,
        used: bool,
        accepted: bool,
        improved: bool,
        retrieval_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Report telemetry for a retrieved lesson."""
        return await _call(
            "report_outcome",
            {
                "lesson_id": lesson_id,
                "used": used,
                "accepted": accepted,
                "improved": improved,
                "retrieval_id": retrieval_id,
                "run_id": run_id,
            },
        )

    @mcp.tool(name="get_policies", annotations=_RO)
    async def get_policies(namespace: str = "global") -> dict[str, Any]:
        """Return active policies visible to a namespace."""
        return await _call("get_policies", {"namespace": namespace})

    @mcp.tool(name="add_policy", annotations=_RW)
    async def add_policy(rule: str, namespace: str = "global", priority: int = 100) -> dict[str, Any]:
        """Add a local policy rule."""
        return await _call("add_policy", {"rule": rule, "namespace": namespace, "priority": priority})

    @mcp.tool(name="add_skill", annotations=_RW)
    async def add_skill(
        name: str,
        description: str,
        steps: list[str],
        workflow: str | None = None,
        tools: list[str] | None = None,
        namespace: str = "global",
        version: str = "0.1.0",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Add a reusable skill/workflow block."""
        return await _call(
            "add_skill",
            {
                "name": name,
                "description": description,
                "steps": steps,
                "workflow": workflow,
                "tools": tools,
                "namespace": namespace,
                "version": version,
                "metadata": metadata,
            },
        )

    @mcp.tool(name="search_skills", annotations=_RO)
    async def search_skills(
        query: str,
        workflow: str | None = None,
        namespace: str = "global",
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Search reusable skills visible to a namespace."""
        return await _call(
            "search_skills",
            {"query": query, "workflow": workflow, "namespace": namespace, "top_k": top_k},
        )

    @mcp.tool(name="get_skill", annotations=_RO)
    async def get_skill(skill_id: str) -> dict[str, Any]:
        """Read a reusable skill by ID."""
        return await _call("get_skill", {"skill_id": skill_id})

    @mcp.tool(name="learn.run.start", annotations=_RW)
    async def learn_run_start(
        workflow_id: str,
        step: str | None = None,
        agents: list[str] | None = None,
        namespace: str | None = None,
        agent: str | None = None,
    ) -> dict[str, Any]:
        return await _call(
            "learn.run.start",
            {
                "workflow_id": workflow_id,
                "step": step,
                "agents": agents or [],
                "namespace": namespace,
                "agent": agent,
            },
        )

    @mcp.tool(name="learn.run.event", annotations=_RW)
    async def learn_run_event(
        run_id: str,
        event_type: str,
        snippet: str | None = None,
        before: str | None = None,
        after: str | None = None,
        intent: str | None = None,
        workflow: str | None = None,
        step: str | None = None,
        agent: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        return await _call(
            "learn.run.event",
            {
                "run_id": run_id,
                "event_type": event_type,
                "snippet": snippet,
                "before": before,
                "after": after,
                "intent": intent,
                "workflow": workflow,
                "step": step,
                "agent": agent,
                "tags": tags or [],
            },
        )

    @mcp.tool(name="learn.run.end", annotations=_RW)
    async def learn_run_end(
        run_id: str,
        success: bool,
        lessons_used: list[str] | None = None,
    ) -> dict[str, Any]:
        return await _call(
            "learn.run.end",
            {"run_id": run_id, "success": success, "lessons_used": lessons_used or []},
        )

    @mcp.tool(name="learn.store", annotations=_RW)
    async def learn_store(lesson_json: str) -> dict[str, Any]:
        return await _call("learn.store", {"lesson_json": lesson_json})

    @mcp.tool(name="learn.retrieve", annotations=_RO)
    async def learn_retrieve(
        query: str,
        workflow: str | None = None,
        step: str | None = None,
        namespace: str | None = None,
        max_tokens: int = 800,
    ) -> dict[str, Any]:
        return await _call(
            "learn.retrieve",
            {
                "query": query,
                "workflow": workflow,
                "step": step,
                "namespace": namespace,
                "max_tokens": max_tokens,
            },
        )

    @mcp.tool(name="learn.reflect", annotations=_RW)
    async def learn_reflect(
        event_ids: list[str] | None = None,
        suggestion: str | None = None,
        failure: str | None = None,
        root_cause: str | None = None,
        fix: str | None = None,
        workflow: str | None = None,
        step: str | None = None,
        auto_promote: bool = False,
    ) -> dict[str, Any]:
        return await _call(
            "learn.reflect",
            {
                "event_ids": event_ids or [],
                "suggestion": suggestion,
                "failure": failure,
                "root_cause": root_cause,
                "fix": fix,
                "workflow": workflow,
                "step": step,
                "auto_promote": auto_promote,
            },
        )

    @mcp.tool(name="learn.validate", annotations=_RW)
    async def learn_validate(
        failure: str,
        fix: str,
        root_cause: str | None = None,
        event_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return await _call(
            "learn.validate",
            {
                "failure": failure,
                "fix": fix,
                "root_cause": root_cause,
                "event_ids": event_ids or [],
            },
        )

    @mcp.tool(name="learn.evaluate", annotations=_RO)
    async def learn_evaluate(run_id: str) -> dict[str, Any]:
        return await _call("learn.evaluate", {"run_id": run_id})

    @mcp.tool(name="learn.feedback", annotations=_RW)
    async def learn_feedback(
        rating: str,
        comment: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        return await _call(
            "learn.feedback",
            {"rating": rating, "comment": comment, "run_id": run_id},
        )

    @mcp.tool(name="learn.improvements", annotations=_RO)
    async def learn_improvements(
        workflow_id: str | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        return await _call(
            "learn.improvements",
            {"workflow_id": workflow_id, "agent_id": agent_id},
        )

    @mcp.tool(name="learn.analytics", annotations=_RO)
    async def learn_analytics() -> dict[str, Any]:
        return await _call("learn.analytics", {})

    @mcp.tool(name="learn.policies", annotations=_RO)
    async def learn_policies() -> dict[str, Any]:
        return await _call("learn.policies", {})

    @mcp.tool(name="learn.experiment", annotations=_RW)
    async def learn_experiment(
        resource_id: str,
        variant_b: str,
        traffic_split: float = 0.1,
    ) -> dict[str, Any]:
        return await _call(
            "learn.experiment",
            {"resource_id": resource_id, "variant_b": variant_b, "traffic_split": traffic_split},
        )

    @mcp.tool(name="learn.rollback", annotations=_DX)
    async def learn_rollback(
        resource_type: str,
        resource_id: str,
        target_version: str,
    ) -> dict[str, Any]:
        return await _call(
            "learn.rollback",
            {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "target_version": target_version,
            },
        )

    @mcp.tool(name="learn.skills", annotations=_RO)
    async def learn_skills(query: str) -> dict[str, Any]:
        return await _call("learn.skills", {"query": query})

    @mcp.tool(name="learn.telemetry", annotations=_RW)
    async def learn_telemetry(
        lesson_id: str,
        run_id: str | None = None,
        used: bool = False,
        accepted: bool = False,
        improved: bool | None = None,
        telemetry_id: str | None = None,
    ) -> dict[str, Any]:
        return await _call(
            "learn.telemetry",
            {
                "lesson_id": lesson_id,
                "run_id": run_id,
                "used": used,
                "accepted": accepted,
                "improved": improved,
                "telemetry_id": telemetry_id,
            },
        )

    @mcp.resource("supermemory://policies/active")
    async def policies_resource() -> str:
        """Active global policies."""
        data = await _call("get_policies", {})
        return json.dumps(data.get("policies", data), indent=2)

    @mcp.resource("supermemory://lessons/{lesson_id}")
    async def lesson_resource(lesson_id: str) -> str:
        """Read a promoted lesson."""
        from supermemory_mcp.handlers import get_service
        svc = await get_service(data_dir)
        lesson = await svc.get_lesson(lesson_id)
        return json.dumps(lesson.model_dump(mode="json") if lesson else {"error": "not_found"}, indent=2)

    @mcp.resource("supermemory://memory/{lesson_id}/provenance")
    async def provenance_resource(lesson_id: str) -> str:
        """Read a lesson provenance chain."""
        from supermemory_mcp.handlers import get_service
        svc = await get_service(data_dir)
        prov = await svc.get_provenance(lesson_id)
        return json.dumps(prov or {"error": "not_found"}, indent=2)

    @mcp.resource("supermemory://skills/{skill_id}")
    async def skill_resource(skill_id: str) -> str:
        """Read a reusable skill."""
        data = await _call("get_skill", {"skill_id": skill_id})
        return json.dumps(data, indent=2)

    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SuperMemory MCP server.")
    parser.add_argument(
        "--storage",
        default=os.getenv("SUPERMEMORY_STORAGE_PATH") or os.getenv("UALL_DATA_DIR") or ".supermemory",
    )
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    args = parser.parse_args()

    if args.transport == "stdio" and sys.stdin.isatty():
        print(
            "SuperMemory MCP server uses stdio transport and must be started by an MCP client "
            "(Cursor, Claude Desktop, Claude Code), not run directly in a terminal.\n"
            "\n"
            "Add to your MCP config:\n"
            '  "command": "supermemory-agent",\n'
            '  "args": ["--storage", ".supermemory", "--transport", "stdio"]\n'
            "\n"
            "Examples: examples/cursor.mcp.json  |  examples/claude_desktop_config.json\n"
            "\n"
            "To run locally for testing, use HTTP transport instead:\n"
            "  supermemory-agent --transport streamable-http\n"
            "\n"
            "Run supermemory-agent --help for all options."
        )
        raise SystemExit(0)

    build_server(args.storage).run(transport=args.transport)


if __name__ == "__main__":
    main()
