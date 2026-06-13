# SuperMemory agent skills

Shared agent skills for **Cursor** and **Claude Code / Claude Desktop**.

## Layout

```
skills/supermemory-agent-learning/     # canonical source (edit here)
.cursor/skills/supermemory-agent-learning/   # Cursor project skill (auto-discovered)
.claude/skills/supermemory-agent-learning/   # Claude Code project skill
```

After editing files under `skills/`, sync copies:

```bash
python scripts/sync_skills.py
```

## Install

Skills ship in the same repo as the MCP server and are bundled in the `supermemory-agent` PyPI wheel.

### Cursor (project)

Already included at `.cursor/skills/supermemory-agent-learning/`.  
Also add MCP: copy `examples/cursor.mcp.json` → `.cursor/mcp.json`.

### Cursor (global)

```bash
cp -r skills/supermemory-agent-learning ~/.cursor/skills/supermemory-agent-learning
```

### Claude Code (project)

Already included at `.claude/skills/supermemory-agent-learning/`.

### Claude Code (global)

```bash
cp -r skills/supermemory-agent-learning ~/.claude/skills/supermemory-agent-learning
```

### Claude Desktop (MCP only)

Add `examples/claude_desktop_config.json` to:

```
%APPDATA%\Claude\claude_desktop_config.json
```

Claude Desktop uses MCP tools; project skills apply in Claude Code.

## Trigger phrases

Mention **SuperMemory**, **agent learning**, **MCP memory**, or **closed-loop lessons** to load the skill.
