# SuperMemory Integration Examples

## Example 1: MCP closed loop (Claude / Cursor)

```
record_failure(summary="Planner skipped schema validation", workflow="sql-pipeline", step="planner")
reflect(event_ids=[...], suggestion="check schema constraints before SQL generation")
validate(reflection_id=...)
process_promotions()
retrieve(query="SQL planner schema", workflow="sql-pipeline", step="planner")
report_outcome(lesson_id=..., used=true, accepted=true, improved=true)
```

## Example 2: Cursor MCP config

Copy `examples/cursor.mcp.json` to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "supermemory": {
      "command": "python",
      "args": ["-m", "supermemory_mcp.server", "--storage", ".supermemory", "--transport", "stdio"],
      "env": {
        "PYTHONPATH": "${workspaceFolder}/src;${workspaceFolder}/packages;${workspaceFolder}",
        "SUPERMEMORY_STORAGE_PATH": ".supermemory"
      }
    }
  }
}
```

## Example 3: Claude Desktop MCP config

Merge `examples/claude_desktop_config.json` into:

```
%APPDATA%\Claude\claude_desktop_config.json
```

Restart Claude Desktop after editing.

## Example 4: Claude Code project skill

Skill is at `.claude/skills/supermemory-agent-learning/`.  
Canonical source: `skills/supermemory-agent-learning/` (sync with `python scripts/sync_skills.py`).

## Example 5: SDK multi-step run

```python
from uall_python import UALLClient

client = UALLClient(storage="file")

with client.run(workflow_id="rag-pipeline", step="planner", namespace="team:ml") as run:
    lessons = run.retrieve(step="planner", query=state["task"])
    if state.get("failed"):
        run.record_failure(snippet=state["error"], agent="planner")
    run.end(success=not state.get("failed"))
```

## Example 6: Remote REST

```python
import httpx

headers = {"X-UALL-Key": "dev-key-change-me"}
r = httpx.post("http://localhost:8000/memory/search", headers=headers, json={
    "query": "SQL join errors",
    "step": "generator",
    "workflow": "sql-pipeline",
    "max_tokens": 800,
})
lessons = r.json()
```

## Example 7: Org policy via MCP

```
add_policy(rule="Never expose secrets", namespace="organization:default")
get_policies()
```

Policies are injected before lessons on every `retrieve` call.
