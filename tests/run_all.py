"""
Run ALL UALL tests: core, MCP, parity, agents, skill.

Usage: python tests/run_all.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPTS = [
    ("pytest core + MCP + parity", [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"]),
    ("single agent MCP", [sys.executable, "examples/mcp_agents/single_agent_mcp.py"]),
    ("multi agent MCP", [sys.executable, "examples/mcp_agents/multi_agent_mcp.py"]),
    ("skill-guided MCP", [sys.executable, "examples/mcp_agents/skill_guided_mcp.py"]),
    ("markdown agents MCP", [sys.executable, "examples/mcp_agents/run_md_agents.py"]),
    ("SDK demo", [sys.executable, "examples/multi_agent_orchestrator/demo.py"]),
]

def main():
    print("=" * 60)
    print("UALL FULL TEST SUITE")
    print("=" * 60)

    passed, failed = 0, 0
    for name, cmd in SCRIPTS:
        print(f"\n--- {name} ---")
        result = subprocess.run(cmd, cwd=ROOT)
        if result.returncode == 0:
            print(f"PASS: {name}")
            passed += 1
        else:
            print(f"FAIL: {name} (exit {result.returncode})")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
