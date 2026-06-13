# GitHub Releases

Every SuperMemory version is published as a [GitHub Release](https://github.com/YashvantHange/SuperMemory/releases) with **installable package assets** attached:

| Asset | Purpose |
|-------|---------|
| `supermemory_agent-{version}-py3-none-any.whl` | Recommended — `pip install` from file |
| `supermemory_agent-{version}.tar.gz` | Source distribution |

Creating a release also triggers CI to publish the same build to **PyPI** and the **MCP Registry**.

## Release checklist

1. Bump version in `pyproject.toml` and `server.json` (keep them in sync).
2. Commit changes with a clear message.
3. Push to `main`.
4. Create a GitHub Release (tag must match version, e.g. `v0.2.4`).

### Option A — GitHub UI

1. Open [New release](https://github.com/YashvantHange/SuperMemory/releases/new).
2. Choose tag `vX.Y.Z` (create from `main` if it does not exist).
3. Title example: `v0.2.4 — Skills bundled + tool safety annotations`
4. Write release notes (what changed since last tag).
5. Click **Publish release**.

The `Publish Release` workflow will:

- Build wheel + sdist
- Attach both files to the release
- Upload to PyPI (`supermemory-agent`)
- Publish `server.json` to the MCP Registry

### Option B — CLI helper

```bash
# After bumping pyproject.toml / server.json and pushing:
python scripts/release.py --title "v0.2.4 — Skills bundled + tool safety annotations"
```

Requires [GitHub CLI](https://cli.github.com/) (`gh`) authenticated.

### Option C — Manual assets only (no CI)

```bash
python -m pip install build
python -m build -n
gh release create v0.2.4 dist/supermemory_agent-0.2.4* \
  --title "v0.2.4 — Skills bundled + tool safety annotations" \
  --generate-notes
```

## Install from a release asset

```bash
pip install https://github.com/YashvantHange/SuperMemory/releases/download/v0.2.4/supermemory_agent-0.2.4-py3-none-any.whl
```

Or download the `.whl` and install locally:

```bash
pip install supermemory_agent-0.2.4-py3-none-any.whl
supermemory-agent --storage .supermemory --transport stdio
```

## Required GitHub secret

Set `PYPI_API_TOKEN` under **Settings → Secrets and variables → Actions** so releases can publish to PyPI automatically.

## Version tags

| Tag | Highlights |
|-----|------------|
| [v0.2.4](https://github.com/YashvantHange/SuperMemory/releases/tag/v0.2.4) | Skills bundled in PyPI wheel; MCP tool safety annotations |
| [v0.2.0](https://github.com/YashvantHange/SuperMemory/releases/tag/v0.2.0) | First MCP Registry + PyPI publish |
