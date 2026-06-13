# Orchestrator Agent

**Role:** Coordinate planner and workers in multi-agent PDF pipeline  
**Workflow:** `pdf-pipeline`  
**Namespace:** `team:eng`

## UALL MCP Tools

1. `learn.run.start` — begin orchestrated run
2. `learn.improvements` — get recommendations before delegating
3. `learn.analytics` — check system health after runs
4. `learn.run.end` — close run with aggregate success

## Delegation

```
Orchestrator → Planner (planner.md) → route decision
            → OCR Worker (ocr_worker.md) if needed
            → Generator (not shown) for output
```

## Multi-agent rules

- Each sub-agent records only its own failures/corrections
- Orchestrator retrieves cross-step lessons for routing decisions
- Use `learn.telemetry` to close the feedback loop
