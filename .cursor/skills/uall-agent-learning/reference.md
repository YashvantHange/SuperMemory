# UALL Module Reference

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
  "freshness": {
    "usage_count": 12,
    "success_after_use": 10,
    "staleness_score": 0.15
  },
  "provenance": {
    "run_id": "run_xyz",
    "reflection_id": "reflection_91",
    "event_ids": ["failure_5"],
    "policy_version": "security_policy:v1"
  },
  "stage": {
    "workflow": "pdf-pipeline",
    "step": "planner",
    "agent": "planner-agent-1"
  },
  "namespace": { "level": "team", "namespace_id": "eng" }
}
```

## Validator actions

| Action | Next step |
|--------|-----------|
| `reject` | Discard — never store |
| `merge` | Increment occurrence_count on existing lesson |
| `rewrite` | Tighten fix text, then approve |
| `approve` | Enqueue to promotion queue |

## Retrieval pipeline stages

1. Namespace filter
2. Metadata filter (workflow, step, tool, agent, domain)
3. Vector similarity (cosine on embeddings)
4. Rerank (sort by composite score)
5. Freshness weighting (`1 - staleness_score`)
6. Confidence weighting (`overall`)
7. Policy injection (fixed prefix, not ranked)

**Score formula:** `semantic * stage_boost * namespace_boost * freshness * ttl * confidence`

## Graph edge types

`caused_by`, `fixed_by`, `supersedes`, `related_to`, `depends_on`, `conflicts_with`, `derived_from`, `generalizes`, `specializes`

Validator checks `conflicts_with` during contradiction detection.

## Experiment guardrails

Promote variant B only if:
- `success_rate` improves
- `latency_p95` does not regress >20%
- `downstream_failure_rate` does not increase >5%

Otherwise trigger rollback via `RollbackManager`.

## File storage layout (`.uall/`)

```
.uall/
├── lessons/          # validated lessons only
├── pending/          # awaiting promotion
├── telemetry/        # retrieval outcomes
├── policies/         # versioned org policies
├── reflections/      # pre-validation
├── skills/           # reusable workflows
└── config.json
```

## Extending LLM provider

Implement `LLMProvider` protocol in `packages/uall_core/providers/llm.py`:

```python
class OpenAIProvider:
    async def complete(self, prompt: str, max_tokens: int = 500) -> str: ...
    async def embed(self, text: str) -> list[float]: ...
```

Wire via env: `UALL_LLM_PROVIDER=openai`. Default is `heuristic` (zero API keys).

## Testing checklist for new features

- [ ] Unit test in `tests/test_uall.py`
- [ ] Works with `FileStorageAdapter`
- [ ] Works with `SQLiteStorageAdapter`
- [ ] Works with `PostgresStorageAdapter` (stub)
- [ ] Demo script still passes if integration-facing
