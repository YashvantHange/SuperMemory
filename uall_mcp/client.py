"""Thin MCP client for agents — calls handlers directly (no stdio)."""

import json
from typing import Any

from uall_mcp.handlers import handle_tool, reset_service


class UALLMCPClient:
    """In-process MCP client for agents, tests, and markdown agent runners."""

    def __init__(self, data_dir: str | None = None):
        self.data_dir = data_dir
        reset_service()

    async def call(self, tool: str, **kwargs) -> Any:
        raw = await handle_tool(tool, kwargs, data_dir=self.data_dir)
        return json.loads(raw)

    async def run_start(self, workflow_id: str, **kwargs) -> dict:
        return await self.call("learn.run.start", workflow_id=workflow_id, **kwargs)

    async def run_event(self, run_id: str, event_type: str, **kwargs) -> dict:
        return await self.call("learn.run.event", run_id=run_id, event_type=event_type, **kwargs)

    async def run_end(self, run_id: str, success: bool, **kwargs) -> dict:
        return await self.call("learn.run.end", run_id=run_id, success=success, **kwargs)

    async def retrieve(self, query: str, **kwargs) -> list:
        result = await self.call("learn.retrieve", query=query, **kwargs)
        if isinstance(result, dict):
            return result.get("lessons", [])
        return result

    async def record_failure(self, summary: str, **kwargs) -> dict:
        return await self.call("record_failure", summary=summary, **kwargs)

    async def reflect(self, failure: str, fix: str, run_id: str | None = None, **kwargs) -> dict:
        """Evidence-first reflect: uses run event or records a standalone failure."""
        if run_id:
            event = await self.run_event(run_id, "failure", snippet=failure, **kwargs)
            event_id = event["event_id"]
        else:
            event = await self.record_failure(
                summary=failure,
                workflow=kwargs.get("workflow"),
                step=kwargs.get("step"),
                namespace=kwargs.get("namespace", "global"),
            )
            event_id = event["id"]
        return await self.call(
            "learn.reflect",
            event_ids=[event_id],
            suggestion=fix,
            auto_promote=True,
        )

    async def telemetry(self, lesson_id: str, **kwargs) -> dict:
        return await self.call("learn.telemetry", lesson_id=lesson_id, **kwargs)

    async def improvements(self, **kwargs) -> list:
        return await self.call("learn.improvements", **kwargs)

    async def policies(self) -> list:
        return await self.call("learn.policies")

    async def analytics(self) -> dict:
        return await self.call("learn.analytics")
