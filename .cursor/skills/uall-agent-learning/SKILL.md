---
name: uall-agent-learning
description: >-
  Build, extend, and integrate the Universal Agent Learning Layer (UALL) for
  multi-agent systems. Use when implementing agent memory, learning from failures,
  reflection pipelines, lesson validation, promotion queues, retrieval telemetry,
  A/B experiments, rollback, or plugging UALL into LangGraph, CrewAI, MCP, or
  custom orchestrator+worker agents. Also use when the user mentions SuperMemory,
  UALL, agent learning layer, distilled lessons, or low-token agent memory.
---

# UALL — Universal Agent Learning Layer

## Core principle (never violate)

UALL is **not** full observability. It captures **workflow outcomes and distilled lessons only** — never full conversation transcripts.

| Capture | When |
|---------|------|
| Workflow snapshot | Run start/end |
| Failure / correction / suggestion | Significant events only |
| Distilled lesson | After reflect → validate → promote |

**Token budget at retrieval:** default `max_tokens=800`. Store lessons, not histories.

---

## Architecture (closed loop)

```
Run → Failure/Correction → Reflect → Validate → Pending Queue → Shadow Test → Promote
                                                                              ↓
Retrieve (policies first) ← Store ← Telemetry ← Run end
```

**Critical gates:** Memory Validator (reject/merge/rewrite/approve) and Promotion Queue (no immediate store).

---

## Project layout

```
packages/uall_core/     # schemas, StoragePort, LLM providers
packages/uall/         # business logic (collector, memory, promotion, etc.)
packages/uall_server/  # FastAPI REST
packages/uall_python/  # SDK (UALLClient)
storage/adapters/      # file (default), sqlite, postgres
mcp/server.py          # learn.* MCP tools (use uall_mcp/server.py)
examples/              # demo + cursor MCP config
tests/                 # integration tests (all tiers)
```

Entry point: `packages/uall/service.py` (`UALLService` orchestrates all modules).

---

## When to use which interface

| Context | Use |
|---------|-----|
| Python agent in same process | `UALLClient(storage="file")` — zero deps |
| Remote / polyglot agents | REST API (`python -m uall_server`, port 8000) |
| Cursor / Claude Code | MCP (`mcp/server.py`) — `learn.retrieve`, `learn.reflect`, etc. |
| Tests | `pytest tests/` — file, sqlite, postgres adapters |

---

## Integration workflow (agent developer)

Copy this checklist:

```
- [ ] 1. Start run with workflow_id + step + namespace
- [ ] 2. Retrieve lessons BEFORE agent step (stage-aware)
- [ ] 3. Inject policies + lessons into system prompt (≤800 tokens)
- [ ] 4. On failure/correction ONLY — record_event (not every LLM turn)
- [ ] 5. Report lesson outcome after run (telemetry)
- [ ] 6. End run with success + lessons_used list
```

### SDK pattern (default)

```python
from uall_python import UALLClient

client = UALLClient(storage="file")  # or base_url="http://localhost:8000" for remote

with client.run(workflow_id="pdf-pipeline", step="planner", namespace="team:eng") as run:
    lessons = run.retrieve(step="planner", query="PDF routing", max_tokens=800)
    # inject lessons into agent prompt ...

    # only on failure:
    run.record_failure(snippet="chose OCR for searchable PDF", tags=["routing"])
    run.record_correction(before="ocr", after="text_layer", intent="searchable PDF")

    if lessons:
        run.report_lesson_outcome(
            lesson_id=lessons[0]["lesson"]["lesson_id"],
            used=True, accepted=True, improved=True,
        )
    run.end(success=True)
```

### Multi-agent (orchestrator + workers)

- **Orchestrator:** `runs/start`, `retrieve(step=...)`, inject context, `runs/end`
- **Workers:** `record_failure` / `record_correction` with `stage.agent` set
- Each worker step carries: `workflow`, `step`, `tool`, `agent`, `domain`, `namespace`

---

## Implementing new features

Follow existing module patterns:

1. **Schema** → `packages/uall_core/schemas/`
2. **Logic** → `packages/uall/<module>/`
3. **Wire into** `UALLService` in `packages/uall/service.py`
4. **REST route** → `packages/uall_server/main.py`
5. **SDK method** → `packages/uall_python/client.py` (if user-facing)
6. **MCP tool** → `mcp/server.py` (if agent-facing)
7. **Test** → `tests/test_uall.py`

### Storage changes

All adapters implement `StoragePort` (`packages/uall_core/ports/storage.py`). Add method to port → implement in `file.py`, `sqlite_chroma.py`, `postgres_qdrant_redis.py`.

### Memory pipeline (when adding learning logic)

```
CandidateLesson → ReflectionEngine → MemoryValidator → PromotionQueue → Lesson
```

Never write directly to `lessons/` without validation. Lessons require `provenance` (run_id, reflection_id, event_ids, policy_version).

---

## Key modules reference

| Module | Path | Purpose |
|--------|------|---------|
| Event Collector | `uall/collector/service.py` | Selective event ingest |
| Reflection | `uall/reflection/engine.py` | LLM/heuristic lesson extraction |
| Validator | `uall/memory/validator.py` | reject/merge/rewrite/approve |
| Promotion Queue | `uall/promotion/queue.py` | Async promote after shadow test |
| Retrieval | `uall/memory/retrieval.py` | Hybrid pipeline (namespace→metadata→vector→rank) |
| Telemetry | `uall/telemetry/retrieval.py` | retrieved→used→accepted→outcome |
| Confidence | `uall/memory/confidence.py` | evidence, retrieval_success, human_verified, overall |
| Experiments | `uall/experiments/manager.py` | A/B with guardrail metrics |
| Rollback | `uall/rollback/manager.py` | Version history + revert |

---

## REST endpoints (quick ref)

| Endpoint | Purpose |
|----------|---------|
| `POST /runs/start`, `/runs/event`, `/runs/end` | Run lifecycle |
| `POST /memory/search` | Stage-aware retrieval |
| `POST /memory/validate` | Validate candidate |
| `POST /promotion/process` | Process pending queue |
| `POST /telemetry/lesson-outcome` | Report lesson usage |
| `GET /policies` | Org policies (injected first) |
| `POST /experiments/start` | A/B test |
| `POST /rollback` | Revert version |

Auth header: `X-UALL-Key` (default: `dev-key-change-me`).

---

## MCP tools (16)

`learn.run.start`, `learn.run.event`, `learn.run.end`, `learn.store`, `learn.retrieve`, `learn.reflect`, `learn.validate`, `learn.evaluate`, `learn.feedback`, `learn.improvements`, `learn.analytics`, `learn.policies`, `learn.experiment`, `learn.rollback`, `learn.skills`, `learn.telemetry`

Config: `examples/cursor_mcp/mcp.json` — runs `python uall_mcp/server.py`

MCP tests: `python -m pytest tests/test_mcp.py -v` and `examples/mcp_agents/*.py`

---

## Storage tiers

| Tier | Env | When |
|------|-----|------|
| File (default) | `UALL_STORAGE_BACKEND=file` | Zero deps, `.uall/` JSON |
| SQLite | `UALL_STORAGE_BACKEND=sqlite` | Local querying |
| Postgres | `UALL_STORAGE_BACKEND=postgres` | Enterprise (docker-compose.yml) |

---

## Verification commands

```bash
pip install -e ".[dev,mcp]"
python -m pytest tests/ -q
python examples/multi_agent_orchestrator/demo.py
python examples/mcp_agents/run_md_agents.py
python -m uall_server
```

Success criteria for integrations:
- Poor reflections rejected by validator
- Approved lessons enter pending queue, not store directly
- Second run retrieves stage-matched lessons and avoids repeated failures
- Telemetry updates confidence dimensions

---

## Anti-patterns

- ❌ Recording every LLM turn or full transcripts
- ❌ Storing lessons without validator + promotion queue
- ❌ Semantic-only retrieval (must filter by step/workflow/namespace)
- ❌ Promoting prompt changes without A/B experiment
- ❌ Skipping `report_lesson_outcome` (breaks recalibration)

---

## Additional resources

- Full API spec: [api/openapi.yaml](../../api/openapi.yaml)
- Integration examples: [examples.md](examples.md)
- Module deep-dive: [reference.md](reference.md)
