# SuperMemory MCP

<!-- mcp-name: io.github.YashvantHange/supermemory -->

MCP-first learning memory layer for Claude, Cursor, and agent workflows. Captures distilled lessons from failures and corrections (not full transcripts), validates before storage, and improves agents over time through a closed-loop cycle.

## Install from PyPI (recommended for Claude / Cursor users)

```bash
pip install supermemory-agent
supermemory-agent --storage .supermemory --transport stdio
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uvx supermemory-agent --storage .supermemory --transport stdio
```

## Install from source (developers)

```bash
pip install -e ".[dev]"
```

## Run MCP server

```bash
python -m supermemory_mcp.server --storage .supermemory --transport stdio
```

Or via CLI entry point:

```bash
supermemory-agent --storage .supermemory --transport stdio
```

Streamable HTTP:

```bash
python -m supermemory_mcp.server --storage .supermemory --transport streamable-http
```

## MCP tools (29 total)

**GitHub-compatible core (13):** `retrieve`, `record_event`, `record_failure`, `record_correction`, `reflect`, `validate`, `process_promotions`, `report_outcome`, `get_policies`, `add_policy`, `add_skill`, `search_skills`, `get_skill`

**Extended UALL (16):** `learn.run.start`, `learn.run.event`, `learn.run.end`, `learn.store`, `learn.retrieve`, `learn.reflect`, `learn.validate`, `learn.evaluate`, `learn.feedback`, `learn.improvements`, `learn.analytics`, `learn.policies`, `learn.experiment`, `learn.rollback`, `learn.skills`, `learn.telemetry`

## MCP resources

- `supermemory://policies/active`
- `supermemory://lessons/{lesson_id}`
- `supermemory://memory/{lesson_id}/provenance`
- `supermemory://skills/{skill_id}`

## Agent learning loop

```
retrieve → record_failure → reflect(event_ids) → validate → process_promotions
         → retrieve again → report_outcome
```

## Cursor / Claude Desktop

### MCP server

Copy `examples/cursor.mcp.json` to `.cursor/mcp.json` (Cursor project).

For Claude Desktop, merge `examples/claude_desktop_config.json` into:

```
%APPDATA%\Claude\claude_desktop_config.json
```

Restart Claude Desktop after editing the config.

### Agent skills (Cursor + Claude Code)

| Platform | Project path | Global path |
|----------|--------------|-------------|
| **Cursor** | `.cursor/skills/supermemory-agent-learning/` | `~/.cursor/skills/supermemory-agent-learning/` |
| **Claude Code** | `.claude/skills/supermemory-agent-learning/` | `~/.claude/skills/supermemory-agent-learning/` |
| **Canonical source** | `skills/supermemory-agent-learning/` | edit here, then run `python scripts/sync_skills.py` |

Mention **SuperMemory**, **agent learning**, or **MCP memory** in chat to load the skill.

## Python SDK

```python
from uall_python import UALLClient

client = UALLClient(storage="file")

with client.run(workflow_id="pdf-pipeline", step="planner", namespace="team:eng") as run:
    lessons = run.retrieve(step="planner", max_tokens=800)
    run.record_failure(snippet="chose OCR for searchable PDF", tags=["routing"])
    run.report_lesson_outcome(lesson_id="lesson_001", used=True, accepted=True, improved=True)
```

## REST API

```bash
python -m uall_server
```

Server runs at `http://localhost:8000`. See `api/openapi.yaml`.

## Storage

| Tier | Backend | Default path |
|------|---------|--------------|
| Default | `.supermemory/` JSON files | `SUPERMEMORY_STORAGE_PATH` or `UALL_DATA_DIR` |
| Optional | SQLite | `UALL_STORAGE_BACKEND=sqlite` |
| Enterprise | PostgreSQL + stubs | `UALL_STORAGE_BACKEND=postgres` |

## Tests

```bash
python tests/run_all.py              # full suite (pytest + agent demos)
python -m pytest tests/ -v           # all unit/integration tests
python -m pytest tests/test_mcp_server.py -v   # real stdio MCP transport
python -m pytest tests/test_core.py -v         # GitHub-compatible closed loop
```

## License

MIT — see [LICENSE](LICENSE)

## Publish / list in directories

See [docs/PUBLISHING.md](docs/PUBLISHING.md) for MCP Registry, Cursor Directory, and Claude Connectors Directory submission steps.
