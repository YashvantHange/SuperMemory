"""Sync canonical skills/ to .cursor/skills and .claude/skills."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills"
TARGETS = [
    ROOT / ".cursor" / "skills",
    ROOT / ".claude" / "skills",
]


def sync() -> int:
    if not SOURCE.exists():
        print(f"Missing skills directory: {SOURCE}", file=sys.stderr)
        return 1

    for skill_dir in SOURCE.iterdir():
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue
        if skill_dir.name == "__pycache__":
            continue
        for target_root in TARGETS:
            dest = target_root / skill_dir.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(skill_dir, dest)
            print(f"Synced {skill_dir.name} -> {dest.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(sync())
