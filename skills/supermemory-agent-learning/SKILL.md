---
name: supermemory-agent-learning
description: >-
  Build and integrate SuperMemory — MCP-first agent learning for Claude, Cursor,
  and custom orchestrators. Use when implementing selective memory capture,
  evidence-first reflection, lesson validation, promotion queues, retrieval
  telemetry, experiments, rollback, or wiring SuperMemory via MCP, REST, or SDK.
  Trigger on SuperMemory, agent learning layer, distilled lessons, or MCP memory.
---

# SuperMemory — Agent Learning Layer

## Core principle (never violate)

SuperMemory is **not** full observability. Capture **workflow outcomes and distilled lessons only** — never full conversation transcripts.

| Capture | When |
|---------|------|
| Workflow snapshot | Run start/end |
| Failure / correction / suggestion | Significant events only |
| Distilled lesson | After reflect(event_ids) → validate → process_promotions |

**Token budget at retrieval:** default `max_tokens=800`. Store lessons, not histories.

---

## Architecture (closed loop)

```
retrieve → record_failure → reflect(event_ids) → validate → process_promotions
         → retrieve again → report_outcome
```

**Critical gates:** Memory Validator (reject/merge/rewrite/approve) and Promotion Queue (no immediate store without validation).

---

## Project layout

```
src/supermemory_mcp/   # FastMCP server (13 core + 16 learn.* tools, MCP resources)
packages/uall/         # UALL engine (validator, promotion, retrieval, experiments)
packages/uall_server/  # FastAPI REST
packages/uall_python/  # Python SDK
storage/adapters/      # file (.supermemory/), sqlite, postgres
skills/                # canonical agent skills (this file)
examples/              # MCP configs + agent demos
tests/                 # 69 tests incl. real stdio MCP transport
```

Entry point: `packages/uall/service.py` (`UALLService`).

---

## When to use which interface

| Context | Use |
|---------|-----|
| Claude / Cursor agents | MCP — `python -m supermemory_mcp.server` |
| Python agent in-process | `UALLClient` from `uall_python` |
| Remote / polyglot | REST — `python -m uall_server` (port 8000) |
| Tests | `python -m pytest tests/ -v` |

---

## Integration workflow (agent developer)

```
- [ ] 1. retrieve — policies + lessons before the step (stage-aware)
- [ ] 2. record_failure / record_correction — selective events only
- [ ] 3. reflect(event_ids) — evidence-first, never free-text-only
- [ ] 4. validate → process_promotions — explicit promotion step
- [ ] 5. retrieve again on next run
- [ ] 6. report_outcome — telemetry recalibrates confidence
```

### MCP pattern (Claude / Cursor)

```
record_failure(summary="...", workflow="pdf-pipeline", step="planner")
reflect(event_ids=[...], suggestion="inspect text layer first")
validate(reflection_id=...)
process_promotions()
retrieve(query="PDF routing", step="planner")
report_outcome(lesson_id=..., used=true, accepted=true, improved=true)
```

### SDK pattern

```python
from uall_python import UALLClient

client = UALLClient(storage="file")

with client.run(workflow_id="pdf-pipeline", step="planner", namespace="team:eng") as run:
    lessons = run.retrieve(step="planner", query="PDF routing", max_tokens=800)
    run.record_failure(snippet="chose OCR for searchable PDF", tags=["routing"])
    if lessons:
        run.report_lesson_outcome(
            lesson_id=lessons[0]["lesson_id"],
            used=True, accepted=True, improved=True,
        )
    run.end(success=True)
```

---

## MCP tools (29 total)

**Core (13):** `retrieve`, `record_event`, `record_failure`, `record_correction`, `reflect`, `validate`, `process_promotions`, `report_outcome`, `get_policies`, `add_policy`, `add_skill`, `search_skills`, `get_skill`

**Extended (16):** `learn.run.start`, `learn.run.event`, `learn.run.end`, `learn.store`, `learn.retrieve`, `learn.reflect`, `learn.validate`, `learn.evaluate`, `learn.feedback`, `learn.improvements`, `learn.analytics`, `learn.policies`, `learn.experiment`, `learn.rollback`, `learn.skills`, `learn.telemetry`

**MCP resources:** `supermemory://policies/active`, `supermemory://lessons/{id}`, `supermemory://memory/{id}/provenance`, `supermemory://skills/{id}`

Config: `examples/cursor.mcp.json` or `examples/claude_desktop_config.json`

---

## Storage

| Tier | Env | Path |
|------|-----|------|
| File (default) | `SUPERMEMORY_STORAGE_PATH` | `.supermemory/` |
| SQLite | `UALL_STORAGE_BACKEND=sqlite` | local DB |
| Postgres | `UALL_STORAGE_BACKEND=postgres` | enterprise stub |

---

## Verification

```bash
pip install -e ".[dev]"
python -m pytest tests/ -q
python -m pytest tests/test_mcp_server.py -v
python examples/mcp_agents/run_md_agents.py
python -m supermemory_mcp.server --storage .supermemory --transport stdio
```

---

## Anti-patterns

- Recording every LLM turn or full transcripts
- reflect without event_ids (hallucinated lessons)
- Storing lessons without validate + process_promotions
- Skipping report_outcome (breaks confidence recalibration)
- Semantic-only retrieval (must filter by step/workflow/namespace)

---

## Additional resources

- Integration examples: [examples.md](examples.md)
- Module deep-dive: [reference.md](reference.md)
- API spec: [api/openapi.yaml](../../api/openapi.yaml)
- Skill install paths: [skills/README.md](../README.md)
