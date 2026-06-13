"""UALL MCP server — delegates to unified SuperMemory MCP server."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from supermemory_mcp.server import main

if __name__ == "__main__":
    main()
