#!/usr/bin/env python3
"""Clean a complete raw Q&A payload without imposing a question-count target."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

FALLBACK_EN = "Not verified from the current product information."
FALLBACK_CN = "当前商品资料未验证，建议补充确认。"
TARGET_KINDS = {"product_fact", "target_review"}
IRRELEVANT = {"irrelevant", "brand_pollution", "wrong_product", "accessory", "garbled"}
CLEAN_HEADERS = [
    "序号", "优先级", "Alexa问题_EN", "Alexa问题_CN", "标准答案_EN", "标准答案_CN",
    "意图分类", "核心关键词", "关键词来源", "卖家精灵指标", "Listing覆盖状态",
    "目标ASIN评论证据数", "竞品评论证据数", "评论证据摘要", "证据ASIN",
    "数据冲突或缺口", "置信度", "建议动作",
]


def normalize_question(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def is_garbled(value: str) -> bool:
    return bool(re.search(r"�|(?:Ã|Â|â€|ðŸ){2,}", value))


def limit_value(value: Any) -> int | None:
    if value in (None, "", "unlimited"):
        return None
    number = int(value)
    if number < 1:
        raise ValueError("max_clean_questions must be 'unlimited' or a positive integer")
    return number


def target_support(row: dict[str, Any], asin: str) -> bool:
    return any(
        isinstance(item, dict)
        and item.get("kind") in TARGET_KINDS
        and str(item.get("source_asin") or "").upper() == asin
        and str(item.get("value") or item.get("excerpt") or "").strip()
        for item in row.get("answer_evidence") or []
    )


def unique(values: list[str], maximum: int | None = None) -> list[str]:
    result: list[str] = []
    for value in values:
        value = " ".join(str(value or "").split())
        if value and value not in result:
            result.append(value)
            if maximum and len(result) >= maximum:
                break
    return result


def clean_payload(raw: dict[str, Any], max_clean_questions: Any = None) -> dict[str, Any]:
    asin = str(raw.get("asin") or "").upper()
    rows = raw.get("rows") or []
    if not rows:
        raise ValueError("raw payload must contain rows")
    if any(str(row.get("目标ASIN") or "").upper() != asin for row in rows):
        raise ValueError("raw payload contains another target ASIN")

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        text = f"{row.get('问题候选_EN', '')} {row.get('问题候选_CN', '')} {row.get('原始关键词', '')}"
        if str(row.get("relevance_status") or "relevant").lower() in IRRELEVANT or is_garbled(text):
            continue
        key = str(row.get("semantic_key") or "").strip() or normalize_question(str(row.get("问题候选_EN") or ""))
        if key:
            groups[key].append(row)

    cleaned: list[dict[str, Any]] = []
    for semantic_key, group in groups.items():
        canonical = Counter(str(row.get("问题候选_EN") or "") for row in group).most_common(1)[0][0]
        primary = next(row for row in group if str(row.get("问题候选_EN") or "") == canonical)
        supported = next((row for row in group if target_support(row, asin)), None)
        answer = supported or primary
        answer_en = str(answer.get("答案候选_EN") or FALLBACK_EN)
        answer_cn = str(answer.get("答案候选_CN") or FALLBACK_CN)
        if supported is None:
            answer_en, answer_cn = FALLBACK_EN, FALLBACK_CN

        target_reviews = {
            (str(row.get("来源ASIN")), str(row.get("评论ID"))) for row in group
            if row.get("来源类型") == "目标评论" and row.get("评论ID") not in (None, "", "无")
        }
        competitor_reviews = {
            (str(row.get("来源ASIN")), str(row.get("评论ID"))) for row in group
            if row.get("来源类型") == "竞品评论" and row.get("评论ID") not in (None, "", "无")
        }
        sources = unique([str(row.get("关键词来源") or "") for row in group])
        metrics = unique([
            str(row.get("卖家精灵指标") or "") for row in group
            if str(row.get("卖家精灵指标") or "") != "未取得"
        ], 3)
        excerpts = unique([
            str(row.get("评论证据摘录") or "") for row in group
            if str(row.get("评论证据摘录") or "") != "0条评论证据"
        ], 3)
        source_asins = unique([
            str(row.get("来源ASIN") or "") for row in group if row.get("来源类型") in {"目标评论", "竞品评论"}
        ])
        keywords = unique([str(row.get("原始关键词") or "") for row in group], 8)
        score = len(group) + len(target_reviews) * 3 + len(competitor_reviews) + (3 if supported else 0) + (2 if metrics else 0)
        priority = "P0" if score >= 12 else "P1" if score >= 5 else "P2"
        zero_reviews = not target_reviews and not competitor_reviews
        gap_values = unique([str(row.get("数据冲突或缺口") or "") for row in group if str(row.get("数据冲突或缺口") or "") not in {"", "无"}], 3)
        gap = "；".join(gap_values) if gap_values else ("未验证" if not supported else "无")
        if zero_reviews:
            gap = f"{gap}；0条评论证据" if gap != "无" else "0条评论证据"
        cleaned.append({
            "序号": 0,
            "优先级": priority,
            "Alexa问题_EN": canonical,
            "Alexa问题_CN": str(primary.get("问题候选_CN") or ""),
            "标准答案_EN": answer_en,
            "标准答案_CN": answer_cn,
            "意图分类": str(primary.get("意图初始标签") or "未分类"),
            "核心关键词": " | ".join(keywords),
            "关键词来源": "多来源" if len(sources) > 1 else (sources[0] if sources else "未取得"),
            "卖家精灵指标": " | ".join(metrics) if metrics else "未取得",
            "Listing覆盖状态": "完整覆盖" if supported else "未覆盖",
            "目标ASIN评论证据数": len(target_reviews),
            "竞品评论证据数": len(competitor_reviews),
            "评论证据摘要": " | ".join(excerpts) if excerpts else "0条评论证据",
            "证据ASIN": ", ".join(source_asins) if source_asins else asin,
            "数据冲突或缺口": gap,
            "置信度": "高" if supported and target_reviews else "中" if supported else "低",
            "建议动作": "保留" if supported else "需要验证",
            "semantic_key": semantic_key,
            "decision_point": str(primary.get("decision_point") or semantic_key),
            "answer_evidence": answer.get("answer_evidence") or [],
            "score": score,
        })

    order = {"P0": 0, "P1": 1, "P2": 2}
    cleaned.sort(key=lambda row: (order[row["优先级"]], -row["score"], row["Alexa问题_EN"].lower()))
    requested = max_clean_questions if max_clean_questions is not None else raw.get("max_clean_questions", "unlimited")
    maximum = limit_value(requested)
    if maximum is not None:
        cleaned = cleaned[:maximum]
    for index, row in enumerate(cleaned, 1):
        row["序号"] = index
    return {"asin": asin, "site": str(raw.get("site") or "US"), "max_clean_questions": requested or "unlimited", "rows": cleaned}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_payload")
    parser.add_argument("output")
    parser.add_argument("--max-clean-questions", default=None)
    args = parser.parse_args()
    raw = json.loads(Path(args.raw_payload).read_text(encoding="utf-8"))
    result = clean_payload(raw, args.max_clean_questions)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(Path(args.output).resolve()), "questions": len(result["rows"]), "max_clean_questions": result["max_clean_questions"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
