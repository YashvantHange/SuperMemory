# SuperMemory

<!-- mcp-name: io.github.YashvantHange/supermemory -->

**MCP-first agent learning layer** for Claude, Cursor, and custom agent workflows.

SuperMemory captures **distilled lessons** from failures and corrections — not full conversation transcripts — validates them before storage, and improves agents over time through a closed-loop cycle.

[![PyPI](https://img.shields.io/pypi/v/supermemory-agent)](https://pypi.org/project/supermemory-agent/)
[![GitHub Release](https://img.shields.io/github/v/release/YashvantHange/SuperMemory)](https://github.com/YashvantHange/SuperMemory/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![MCP Registry](https://img.shields.io/badge/MCP-io.github.YashvantHange%2Fsupermemory-green)](https://registry.modelcontextprotocol.io)

---

## Quick start

```bash
pip install supermemory-agent
supermemory-agent --storage .supermemory --transport stdio
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uvx supermemory-agent --storage .supermemory --transport stdio
```

**Latest release:** [v0.2.4](https://github.com/YashvantHange/SuperMemory/releases/tag/v0.2.4) — wheel + sdist attached on every [GitHub Release](https://github.com/YashvantHange/SuperMemory/releases).

---

## What you get

| Component | Description |
|-----------|-------------|
| **MCP server** | 29 tools + 4 resources over stdio (or streamable HTTP) |
| **Agent skill** | `skills/supermemory-agent-learning/SKILL.md` — bundled in the PyPI package |
| **Python SDK** | In-process integration via `uall_python` |
| **REST API** | FastAPI server for remote / polyglot clients |
| **Storage** | Local `.supermemory/` files by default; SQLite and PostgreSQL optional |

Everything lives in one repo: MCP server, skills, SDK, REST API, tests, and release packages.

---

## Install

### PyPI (recommended)

```bash
pip install supermemory-agent
```

After install, bundled skills are at `site-packages/skills/supermemory-agent-learning/`. Copy to your editor skills folder if needed.

### GitHub Release (offline / pinned version)

Each release ships installable assets:

```bash
pip install https://github.com/YashvantHange/SuperMemory/releases/download/v0.2.4/supermemory_agent-0.2.4-py3-none-any.whl
```

Browse all versions: [github.com/YashvantHange/SuperMemory/releases](https://github.com/YashvantHange/SuperMemory/releases)

### From source (developers)

```bash
git clone https://github.com/YashvantHange/SuperMemory.git
cd SuperMemory
pip install -e ".[dev]"
python -m pytest tests/ -v
```

---

## Configure MCP

### Cursor

Copy `examples/cursor.mcp.json` to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "supermemory": {
      "command": "supermemory-agent",
      "args": ["--storage", ".supermemory", "--transport", "stdio"]
    }
  }
}
```

### Claude Desktop

Merge `examples/claude_desktop_config.json` into:

```
%APPDATA%\Claude\claude_desktop_config.json
```

Restart Claude Desktop after saving.

### Run manually

Do **not** run `supermemory-agent` alone in a terminal — stdio mode expects JSON-RPC from an MCP client. Pressing Enter in the shell causes a JSON parse error.

```bash
# For local HTTP testing only:
supermemory-agent --transport streamable-http
```

When configured in Cursor or Claude Desktop, the client launches the server automatically over stdio.

---

## Agent skills (Cursor + Claude Code)

| Source | Path |
|--------|------|
| **Canonical** (edit here) | `skills/supermemory-agent-learning/` |
| **Cursor project** | `.cursor/skills/supermemory-agent-learning/` |
| **Claude Code project** | `.claude/skills/supermemory-agent-learning/` |
| **PyPI install** | `site-packages/skills/supermemory-agent-learning/` |

After editing `skills/`, sync copies:

```bash
python scripts/sync_skills.py
```

Mention **SuperMemory**, **agent learning**, or **MCP memory** in chat to load the skill.

---

## Learning loop

```
retrieve → record_failure → reflect(event_ids) → validate → process_promotions
         → retrieve again → report_outcome
```

**Core rule:** capture workflow outcomes and distilled lessons only — never full transcripts. Default retrieval budget: `max_tokens=800`.

---

## MCP tools (29)

**Core (13):** `retrieve`, `record_event`, `record_failure`, `record_correction`, `reflect`, `validate`, `process_promotions`, `report_outcome`, `get_policies`, `add_policy`, `add_skill`, `search_skills`, `get_skill`

**Extended UALL (16):** `learn.run.start`, `learn.run.event`, `learn.run.end`, `learn.store`, `learn.retrieve`, `learn.reflect`, `learn.validate`, `learn.evaluate`, `learn.feedback`, `learn.improvements`, `learn.analytics`, `learn.policies`, `learn.experiment`, `learn.rollback`, `learn.skills`, `learn.telemetry`

All tools include MCP safety annotations (`readOnlyHint` / `destructiveHint`).

## MCP resources (4)

- `supermemory://policies/active`
- `supermemory://lessons/{lesson_id}`
- `supermemory://memory/{lesson_id}/provenance`
- `supermemory://skills/{skill_id}`

---

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

Server: `http://localhost:8000` — see `api/openapi.yaml`.

---

## Storage

| Tier | Backend | Config |
|------|---------|--------|
| Default | `.supermemory/` JSON files | `SUPERMEMORY_STORAGE_PATH` or `UALL_DATA_DIR` |
| Optional | SQLite | `UALL_STORAGE_BACKEND=sqlite` |
| Enterprise | PostgreSQL | `UALL_STORAGE_BACKEND=postgres` |

---

## Project layout

```
SuperMemory/
├── src/supermemory_mcp/          # MCP server (29 tools, 4 resources)
├── skills/supermemory-agent-learning/   # Agent skill (SKILL.md)
├── packages/uall/                # Core learning engine
├── packages/uall_python/         # Python SDK
├── packages/uall_server/         # REST API
├── examples/                     # Cursor + Claude Desktop MCP configs
├── tests/                        # 74 tests incl. stdio MCP transport
└── docs/                         # Publishing, releases, privacy
```

---

## Tests

```bash
python -m pytest tests/ -v
python -m pytest tests/test_mcp_server.py -v   # real stdio MCP transport
python -m pytest tests/test_core.py -v         # closed-loop integration
```

---

## Docs

| Doc | Purpose |
|-----|---------|
| [docs/RELEASES.md](docs/RELEASES.md) | Release checklist — every tag ships wheel + sdist |
| [docs/PUBLISHING.md](docs/PUBLISHING.md) | PyPI, MCP Registry, Cursor & Claude directories |
| [PRIVACY.md](PRIVACY.md) | Privacy policy |
| [skills/README.md](skills/README.md) | Agent skill install paths |

**MCP Registry name:** `io.github.YashvantHange/supermemory`  
**PyPI package:** `supermemory-agent`

---

## License

MIT — see [LICENSE](LICENSE)
