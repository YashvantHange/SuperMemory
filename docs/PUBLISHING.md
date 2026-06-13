# Publishing SuperMemory to official MCP directories

This guide covers listing SuperMemory so **any Claude or Cursor user** can discover and install it.

## What is already in the repo

| Asset | Purpose |
|-------|---------|
| `server.json` | Official [MCP Registry](https://registry.modelcontextprotocol.io) metadata |
| `.mcp.json` | Cursor Directory auto-detection ([Open Plugins](https://open-plugins.com)) |
| `examples/claude_desktop_config.json` | Claude Desktop MCP config |
| `.github/workflows/publish.yml` | Build wheel/sdist, attach to GitHub Release, PyPI + MCP Registry |

README includes the PyPI ownership marker:

```html
<!-- mcp-name: io.github.YashvantHange/supermemory -->
```

---

## 1. Official MCP Registry (Claude + Cursor + all MCP clients)

**Registry:** https://registry.modelcontextprotocol.io  
**Server name:** `io.github.YashvantHange/supermemory`  
**PyPI package:** `supermemory-agent`

### One-time setup

1. Create a [PyPI account](https://pypi.org/account/register/) and API token.
2. Add GitHub repo secret: `PYPI_API_TOKEN`  
   GitHub → **Settings → Secrets and variables → Actions → New repository secret**
3. (Optional) Configure [PyPI trusted publishing](https://docs.pypi.org/trusted-publishers/) for GitHub Actions OIDC instead of a token.
4. Install publisher CLI locally (optional):

   ```bash
   npm install -g mcp-publisher
   ```

### Publish (automated — recommended)

1. Bump `version` in `pyproject.toml` and `server.json`, commit, and push to `main`.
2. Create a [GitHub Release](https://github.com/YashvantHange/SuperMemory/releases/new) with tag `vX.Y.Z` (must match version).
3. The **Publish Release** workflow runs automatically:
   - Builds `supermemory_agent-X.Y.Z-py3-none-any.whl` and `.tar.gz`
   - Uploads both as release assets
   - Publishes to PyPI
   - Publishes to MCP Registry
4. Verify:

   ```bash
   curl "https://registry.modelcontextprotocol.io/v0/servers?search=io.github.YashvantHange/supermemory"
   pip index versions supermemory-agent
   ```

Or use the helper:

```bash
python scripts/release.py --title "v0.2.4 — short summary"
```

See [docs/RELEASES.md](RELEASES.md) for the full checklist.

### Publish (manual)

```bash
pip install build twine
python -m build
twine upload dist/*

mcp-publisher login github
mcp-publisher publish
```

### User install (after PyPI publish)

```bash
pip install supermemory-agent
supermemory-agent --storage .supermemory --transport stdio
```

Or with `uvx`:

```bash
uvx supermemory-agent --storage .supermemory --transport stdio
```

---

## 2. Cursor Directory (community plugin catalog)

**URL:** https://cursor.directory/plugins/new

### Steps

1. Sign in with GitHub or Google.
2. Submit repo URL: `https://github.com/YashvantHange/SuperMemory`
3. Cursor auto-detects from the repo:
   - **MCP servers** — `.mcp.json` (repo root)
   - **Skills** — `.cursor/skills/supermemory-agent-learning/SKILL.md`
   - **Agents** — `examples/mcp_agents/agents/*.md` (optional)

No pull request needed — submission is via the web UI.

---

## 3. Claude Connectors Directory (Anthropic official)

**Docs:** https://claude.com/docs/connectors/directory

Anthropic vets servers for security before listing in Claude.ai, Claude Desktop, Claude Code, and mobile.

### Options

| Path | Requirement |
|------|-------------|
| **Team/Enterprise portal** | Claude.ai → Admin Settings → Connectors → Submit |
| **Individual / no Team plan** | [MCP directory submission form](https://claude.com/docs/connectors/building/submission) (linked from Anthropic docs) |
| **Desktop extension (MCPB)** | Separate desktop extension form |

### Before submitting

- [ ] Server on official MCP Registry (step 1)
- [ ] Public README + install docs
- [ ] Every tool tested via MCP Inspector
- [ ] Evidence-first flow documented (`reflect` requires `event_ids`)
- [ ] Privacy policy URL (can use GitHub repo + LICENSE for open source)
- [ ] Test credentials if remote auth is required (SuperMemory is local-first — not required)

### Review criteria

https://claude.com/docs/connectors/building/review-criteria

---

## 4. Claude Desktop (manual config — works today)

Merge `examples/claude_desktop_config.json` into:

```
%APPDATA%\Claude\claude_desktop_config.json
```

After PyPI publish, users can use:

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

---

## 5. Claude Code skills

Project skill (already in repo):

```
.claude/skills/supermemory-agent-learning/
```

Global install:

```bash
cp -r skills/supermemory-agent-learning ~/.claude/skills/supermemory-agent-learning
```

---

## Checklist

- [ ] GitHub Release `v0.2.4` with wheel + sdist assets (see [RELEASES.md](RELEASES.md))
- [ ] `PYPI_API_TOKEN` secret set for CI
- [ ] MCP Registry shows `io.github.YashvantHange/supermemory`
- [ ] Submit to [cursor.directory](https://cursor.directory/plugins/new)
- [ ] Submit to [Claude Connectors Directory](https://claude.com/docs/connectors/building/submission)
- [ ] Announce: `pip install supermemory-agent`
