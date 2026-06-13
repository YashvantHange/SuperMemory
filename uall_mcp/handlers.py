"""UALL MCP handlers — re-exports unified SuperMemory handlers."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supermemory_mcp.handlers import (  # noqa: F401
    GITHUB_TOOLS,
    LEARN_TOOLS,
    TOOLS,
    get_service,
    handle_tool,
    reset_service,
)

__all__ = [
    "GITHUB_TOOLS",
    "LEARN_TOOLS",
    "TOOLS",
    "get_service",
    "handle_tool",
    "reset_service",
]
