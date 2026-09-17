#!/usr/bin/env python3
"""Validate source-preserving raw Alexa Q&A rows before workbook generation."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
FALLBACK_EN = "Not verified from the current product information."
FALLBACK_CN = "当前商品资料未验证，建议补充确认。"
HEADERS = [
    "记录ID", "目标ASIN", "Amazon站点", "问题候选_EN", "问题候选_CN",
    "答案候选_EN", "答案候选_CN", "原始关键词", "关键词来源", "来源查询词",
    "意图初始标签", "卖家精灵指标", "来源ASIN", "来源类型", "评论ID",
    "评论证据摘录", "证据归属", "Listing事实依据", "数据冲突或缺口", "采集状态",
]
KEYWORD_SOURCES = {"Amazon Listing", "Amazon联想词", "卖家精灵"}
SOURCE_TYPES = {"Listing事实", "关键词", "目标评论", "竞品评论"}
ATTRIBUTIONS = {"目标商品", "竞品", "无评论证据"}
TARGET_KINDS = {"product_fact", "target_review"}


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    asin = str(payload.get("asin") or "").upper()
    if not ASIN_RE.fullmatch(asin):
        errors.append("asin: invalid ASIN")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        return errors + ["rows: at least one raw source row is required"]

    seen_ids: set[str] = set()
    for index, row in enumerate(rows, 1):
        prefix = f"rows[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix}: row must be an object")
            continue
        for field in HEADERS:
            if field not in row or row[field] in (None, ""):
                errors.append(f"{prefix}.{field}: required")

        record_id = str(row.get("记录ID") or "")
        if record_id in seen_ids:
            errors.append(f"{prefix}.记录ID: duplicate")
        seen_ids.add(record_id)
        if str(row.get("目标ASIN") or "").upper() != asin:
            errors.append(f"{prefix}.目标ASIN: must equal payload asin")
        source_asin = str(row.get("来源ASIN") or "").upper()
        if not ASIN_RE.fullmatch(source_asin):
            errors.append(f"{prefix}.来源ASIN: invalid ASIN")
        if row.get("关键词来源") not in KEYWORD_SOURCES:
            errors.append(f"{prefix}.关键词来源: invalid value")
        source_type = row.get("来源类型")
        if source_type not in SOURCE_TYPES:
            errors.append(f"{prefix}.来源类型: invalid value")
        attribution = row.get("证据归属")
        if attribution not in ATTRIBUTIONS:
            errors.append(f"{prefix}.证据归属: invalid value")

        trace = row.get("trace_evidence") or []
        if not trace or not all(str(item.get("value") or "").strip() for item in trace if isinstance(item, dict)):
            errors.append(f"{prefix}.trace_evidence: real source trace required")

        review_id = str(row.get("评论ID") or "")
        excerpt = str(row.get("评论证据摘录") or "")
        mapping = row.get("review_mapping") or {}
        if source_type in {"目标评论", "竞品评论"}:
            if review_id == "无" or excerpt == "0条评论证据":
                errors.append(f"{prefix}: review source requires review ID and excerpt")
            if (
                str(mapping.get("review_id") or "") != review_id
                or str(mapping.get("source_asin") or "").upper() != source_asin
                or str(mapping.get("query") or "") != str(row.get("来源查询词") or "")
            ):
                errors.append(f"{prefix}.review_mapping: review ID, ASIN, or query mismatch")
            expected_type = "目标评论" if source_asin == asin else "竞品评论"
            expected_attr = "目标商品" if source_asin == asin else "竞品"
            if source_type != expected_type or attribution != expected_attr:
                errors.append(f"{prefix}: review ownership mismatch")
        else:
            if review_id != "无":
                errors.append(f"{prefix}.评论ID: non-review row must be 无")
            if attribution != "无评论证据" or "0条评论证据" not in str(row.get("采集状态") or ""):
                errors.append(f"{prefix}: zero-review source must be explicitly marked")

        answer_en = str(row.get("答案候选_EN") or "").strip()
        answer_cn = str(row.get("答案候选_CN") or "").strip()
        is_fallback = answer_en == FALLBACK_EN and answer_cn == FALLBACK_CN
        if (answer_en == FALLBACK_EN) != (answer_cn == FALLBACK_CN):
            errors.append(f"{prefix}: fallback answers must be bilingual")
        target_support = any(
            isinstance(evidence, dict)
            and evidence.get("kind") in TARGET_KINDS
            and str(evidence.get("source_asin") or "").upper() == asin
            and str(evidence.get("value") or evidence.get("excerpt") or "").strip()
            for evidence in (row.get("answer_evidence") or [])
        )
        if not is_fallback and not target_support:
            errors.append(f"{prefix}.答案候选_EN: affirmative answer lacks target-ASIN evidence")
        if not payload.get("seller_sprite_available") and row.get("卖家精灵指标") != "未取得":
            errors.append(f"{prefix}.卖家精灵指标: must be 未取得 when SellerSprite is unavailable")

    return errors


def main(path: str) -> int:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = validate_payload(payload)
    candidates = {str(row.get("candidate_id") or "") for row in payload.get("rows") or []}
    print(json.dumps({
        "ok": not errors,
        "row_count": len(payload.get("rows") or []),
        "candidate_count": len(candidates - {""}),
        "errors": errors,
    }, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate_payload.py PAYLOAD.json")
    raise SystemExit(main(sys.argv[1]))
