"""Heuristic LLM provider — zero API keys required for local dev."""

import hashlib
import math
import re


class HeuristicLLMProvider:
    async def complete(self, prompt: str, max_tokens: int = 500) -> str:
        text = prompt.lower()
        failure = _extract_field(prompt, "failure") or "unknown failure"
        root = _extract_field(prompt, "root cause") or _infer_root(failure)
        fix = _extract_field(prompt, "fix") or _infer_fix(failure, root)
        return f"FAILURE: {failure}\nROOT_CAUSE: {root}\nFIX: {fix}\nCONFIDENCE: 0.85"

    async def embed(self, text: str) -> list[float]:
        tokens = re.findall(r"\w+", text.lower())
        vec = [0.0] * 128
        for tok in tokens:
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            for i in range(128):
                vec[i] += math.sin(h * (i + 1) * 0.001)
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


def _extract_field(prompt: str, label: str) -> str | None:
    for line in prompt.splitlines():
        if label.lower() in line.lower() and ":" in line:
            return line.split(":", 1)[1].strip()[:200]
    return None


def _infer_root(failure: str) -> str:
    if "ocr" in failure.lower():
        return "Routing logic did not inspect PDF text layer before choosing OCR"
    if "sql" in failure.lower() or "join" in failure.lower():
        return "Schema relationships were not verified before generating SQL"
    return "Insufficient validation before action"


def _infer_fix(failure: str, root: str) -> str:
    if "ocr" in failure.lower() or "pdf" in failure.lower():
        return "Inspect PDF text layer first; use OCR only for scanned documents"
    if "sql" in failure.lower():
        return "Inspect foreign keys and schema before generating joins"
    return f"Add validation step to prevent: {root[:80]}"


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
