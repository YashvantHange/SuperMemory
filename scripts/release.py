#!/usr/bin/env python3
"""Build packages and create a GitHub release with wheel + sdist assets."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
SERVER_JSON = ROOT / "server.json"


def read_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit("Could not read version from pyproject.toml")
    return match.group(1)


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT, check=check, text=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", help="Release title (default: v{version} — SuperMemory release)")
    parser.add_argument("--notes", help="Release notes file path")
    parser.add_argument("--notes-text", help="Inline release notes")
    parser.add_argument("--draft", action="store_true", help="Create a draft release")
    parser.add_argument("--skip-build", action="store_true", help="Reuse existing dist/ artifacts")
    args = parser.parse_args()

    version = read_version()
    tag = f"v{version}"
    title = args.title or f"v{version} — SuperMemory release"

    if not args.skip_build:
        run([sys.executable, "-m", "pip", "install", "build"])
        run([sys.executable, "-m", "build", "-n"])

    dist = ROOT / "dist"
    assets = sorted(dist.glob(f"supermemory_agent-{version}*"))
    if not assets:
        raise SystemExit(f"No build artifacts found in {dist} for version {version}")

    cmd = ["gh", "release", "create", tag, *[str(a) for a in assets], "--title", title]
    if args.draft:
        cmd.append("--draft")
    if args.notes:
        cmd.extend(["--notes-file", args.notes])
    elif args.notes_text:
        cmd.extend(["--notes", args.notes_text])
    else:
        cmd.extend(["--generate-notes"])

    run(cmd)
    print(f"Created {tag} with {len(assets)} package asset(s).")
    print(f"https://github.com/YashvantHange/SuperMemory/releases/tag/{tag}")


if __name__ == "__main__":
    main()
