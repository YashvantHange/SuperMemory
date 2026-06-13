# SuperMemory Module Reference

## Lesson schema (stored artifact)

```json
{
  "lesson_id": "lesson_abc123",
  "failure": "chose OCR for searchable PDF",
  "root_cause": "did not inspect text layer",
  "fix": "Inspect PDF text layer first; use OCR only for scanned documents",
  "confidence": {
    "evidence": 0.85,
    "retrieval_success": 0.72,
    "human_verified": false,
    "overall": 0.78
  },
  "provenance": {
    "run_id": "run_xyz",
    "reflection_id": "reflection_91",
    "event_ids": ["event_abc"],
    "policy_version": "security_policy:v1"
  },
  "stage": {
    "workflow": "pdf-pipeline",
    "step": "planner"
  }
}
```

## Validator actions

| Action | Next step |
|--------|-----------|
| `reject` | Discard — never store |
| `merge` | Merge into existing lesson |
| `rewrite` | Tighten fix text, then approve |
| `approve` | Enqueue to promotion queue |

## Promotion flow

```
validate (approve) → pending queue → process_promotions → active lesson
```

Never call `process_promotions` inside `reflect` — keep steps explicit for agents.

## Retrieval pipeline

1. Policies (injected first, not ranked)
2. Namespace + metadata filter
3. Vector similarity
4. Rerank by composite score
5. Freshness + confidence weighting
6. Token budget trim (default 800)

## File storage layout (`.supermemory/`)

```
.supermemory/
├── events/       # indexed evidence events
├── lessons/      # promoted lessons
├── pending/      # awaiting promotion
├── telemetry/    # retrieval outcomes
├── policies/     # versioned org policies
├── reflections/  # pre-validation candidates
└── skills/       # reusable workflow blocks
```

## Key modules

| Module | Path |
|--------|------|
| UALLService | `packages/uall/service.py` |
| MCP handlers | `src/supermemory_mcp/handlers.py` |
| FastMCP server | `src/supermemory_mcp/server.py` |
| Validator | `packages/uall/memory/validator.py` |
| Promotion queue | `packages/uall/promotion/queue.py` |
| Retrieval | `packages/uall/memory/retrieval.py` |
| Telemetry | `packages/uall/telemetry/retrieval.py` |

## Testing checklist

- [ ] `python -m pytest tests/test_core.py` — GitHub-compatible loop
- [ ] `python -m pytest tests/test_mcp_server.py` — real stdio MCP
- [ ] `python examples/mcp_agents/run_md_agents.py` — markdown agents
- [ ] Evidence-first: reflect rejects missing event_ids
