# UALL Integration Examples

## Example 1: LangGraph-style step hook

```python
from uall_python import UALLClient

client = UALLClient(storage="file")

def planner_node(state):
    with client.run(workflow_id="rag-pipeline", step="planner", namespace="team:ml") as run:
        lessons = run.retrieve(step="planner", query=state["task"])
        context = "\n".join(l["lesson"]["fix"] for l in lessons)
        # call LLM with context + state["task"]
        if state.get("failed"):
            run.record_failure(snippet=state["error"], agent="planner")
        run.end(success=not state.get("failed"))
    return state
```

## Example 2: Remote HTTP client

```python
import httpx

headers = {"X-UALL-Key": "dev-key-change-me"}
base = "http://localhost:8000"

# Retrieve
r = httpx.post(f"{base}/memory/search", headers=headers, json={
    "query": "SQL join errors",
    "step": "generator",
    "workflow": "sql-pipeline",
    "max_tokens": 800,
})
lessons = r.json()
```

## Example 3: MCP in Cursor

Add to `.cursor/mcp.json` (see `examples/cursor_mcp/mcp.json`):

```json
{
  "mcpServers": {
    "uall": {
      "command": "python",
      "args": ["uall_mcp/server.py"],
      "env": { "UALL_STORAGE_BACKEND": "file", "UALL_DATA_DIR": ".uall" }
    }
  }
}
```

Then invoke `learn.retrieve` with `{ "query": "PDF routing", "step": "planner" }`.

## Example 4: Adding a new REST endpoint

1. Add method to `UALLService` in `packages/uall/service.py`
2. Add route in `packages/uall_server/main.py`
3. Add test in `tests/test_uall.py`
4. Optionally expose via MCP in `mcp/server.py`

## Example 5: Custom storage adapter

```python
from uall_core.ports.storage import StoragePort

class MyStorageAdapter:
    async def init(self): ...
    async def save_lesson(self, lesson) -> str: ...
    # implement all StoragePort methods

# Register in storage/adapters/file.py get_storage()
```

## Example 6: A/B prompt experiment before rollout

```python
client = UALLClient(storage="file")
exp = client.experiment(
    prompt_id="planner",
    variant_b="Always validate schema before generating SQL",
    split=0.1,
)
# Run 30+ times on variant B, then POST /experiments/end
# Promote only if success_rate improves without latency regression
```

## Example 7: Org policy injection

Policies load automatically on retrieval (prepended, not ranked). Add via API:

```python
from uall_core.schemas.common import PolicyVersion
# POST /policies with PolicyVersion(policy_id="security", version="v2", rules=[...])
```

Lessons validated under old policy versions are flagged for re-validation on policy upgrade.
