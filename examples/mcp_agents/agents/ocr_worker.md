# OCR Worker Agent

**Role:** Extract text from scanned PDFs via OCR  
**Workflow:** `pdf-pipeline`  
**Step:** `ocr`  
**Namespace:** `team:eng`

## UALL MCP Tools

1. `learn.retrieve` — `{ query: "OCR failures", step: "ocr" }`
2. `learn.run.event` — report `workflow_step` or `failure` events only
3. `learn.reflect` — on repeated OCR failures with fix suggestion

## Behavior

- Only invoked when planner routes to OCR path
- Report failures when OCR returns empty text on searchable PDFs
