# Planner Agent

**Role:** Route documents to the correct processing pipeline  
**Workflow:** `pdf-pipeline`  
**Step:** `planner`  
**Namespace:** `team:eng`

## UALL MCP Tools (use in order)

1. `learn.run.start` — `{ workflow_id: "pdf-pipeline", step: "planner", agent: "planner-agent" }`
2. `learn.retrieve` — `{ query: "PDF routing", step: "planner", workflow: "pdf-pipeline" }`
3. `learn.policies` — load org policies before acting
4. On failure → `learn.run.event` — `{ event_type: "failure", snippet: "..." }`
5. On correction → `learn.run.event` — `{ event_type: "correction", before, after, intent }`
6. `learn.telemetry` — report lesson outcome after using retrieved lessons
7. `learn.run.end` — `{ success: true/false, lessons_used: [...] }`

## Decision logic

- If PDF has searchable text layer → route to `text_layer`
- If scanned/image-only PDF → route to `ocr`
- If unsure → inspect text layer first (lesson from UALL)

## Skill reference

Follow `skills/supermemory-agent-learning/SKILL.md` — selective capture only, no full transcripts.
