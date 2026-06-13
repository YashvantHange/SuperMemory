"""Validate server.json for MCP Registry submission."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_JSON = ROOT / "server.json"
README = ROOT / "README.md"

MCP_NAME = "io.github.YashvantHange/supermemory"


def test_server_json_exists_and_valid():
    assert SERVER_JSON.exists()
    data = json.loads(SERVER_JSON.read_text(encoding="utf-8"))
    assert data["name"] == MCP_NAME
    assert len(data["description"]) <= 100
    assert data["packages"][0]["registryType"] == "pypi"
    assert data["packages"][0]["identifier"] == "supermemory-agent-mcp"


def test_readme_has_mcp_name_marker():
    text = README.read_text(encoding="utf-8")
    assert f"mcp-name: {MCP_NAME}" in text


def test_cursor_mcp_json_exists():
    mcp = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    assert "supermemory" in mcp["mcpServers"]
