## What's new

- Bundle `skills/` in PyPI wheel and sdist (MCP server + `SKILL.md` ship together)
- Add `readOnlyHint` / `destructiveHint` on all 29 MCP tools (Claude Directory requirement)
- Document monorepo layout in README
- GitHub Releases now attach wheel + sdist on every tag (CI + `scripts/release.py`)
- 74 tests passing

## Install

```bash
pip install supermemory-agent==0.2.4
# or from this release asset:
pip install supermemory_agent-0.2.4-py3-none-any.whl
supermemory-agent --storage .supermemory --transport stdio
```

## Assets

- `supermemory_agent-0.2.4-py3-none-any.whl` — recommended
- `supermemory_agent-0.2.4.tar.gz` — source distribution
