from __future__ import annotations

import json
from typing import Any


def bounded_text(value: Any, limit: int) -> str:
    if isinstance(value, dict):
        text = json.dumps(value, default=str)
    else:
        text = str(value)
    return text[:limit]


def merge_text(parts: list[str], limit: int) -> str:
    return bounded_text(" ".join(part for part in parts if part), limit)
