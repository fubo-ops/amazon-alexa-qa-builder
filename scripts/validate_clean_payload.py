#!/usr/bin/env python3
"""Validate cleaned Alexa Q&A payloads and answer-evidence boundaries."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from .clean_payload import CLEAN_HEADERS, FALLBACK_CN, FALLBACK_EN, TARGET_KINDS
except ImportError:
    from clean_payload import CLEAN_HEADERS, FALLBACK_CN, FALLBACK_EN, TARGET_KINDS

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")


def validate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    asin = str(payload.get("asin") or "").upper()
    if not ASIN_RE.fullmatch(asin):
        errors.append("asin: invalid")
    if payload.get("max_clean_questions") in (None, ""):
        errors.append("max_clean_questions: required")
    rows = payload.get("rows") or []
    if not rows:
        return errors + ["rows: required"]
    keys: set[str] = set()
    for index, row in enumerate(rows, 1):
        prefix = f"rows[{index}]"
        for field in CLEAN_HEADERS:
            if field not in row or row[field] in (None, ""):
                errors.append(f"{prefix}.{field}: required")
        key = str(row.get("semantic_key") or "")
        if not key or key in keys:
            errors.append(f"{prefix}.semantic_key: missing or duplicate")
        keys.add(key)
        answer_en = str(row.get("标准答案_EN") or "")
        answer_cn = str(row.get("标准答案_CN") or "")
        fallback = answer_en == FALLBACK_EN and answer_cn == FALLBACK_CN
        support = any(
            isinstance(item, dict) and item.get("kind") in TARGET_KINDS
            and str(item.get("source_asin") or "").upper() == asin
            and str(item.get("value") or item.get("excerpt") or "").strip()
            for item in row.get("answer_evidence") or []
        )
        if not fallback and not support:
            errors.append(f"{prefix}.标准答案_EN: affirmative answer lacks target evidence")
    return errors


def main(path: str) -> int:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = validate(payload)
    print(json.dumps({"ok": not errors, "question_count": len(payload.get("rows") or []), "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate_clean_payload.py CLEAN_PAYLOAD.json")
    raise SystemExit(main(sys.argv[1]))
