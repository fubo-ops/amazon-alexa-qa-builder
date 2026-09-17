#!/usr/bin/env python3
"""Expand candidates and Rufus mappings into source-preserving raw Q&A rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Optional

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
FALLBACK_EN = "Not verified from the current product information."
FALLBACK_CN = "当前商品资料未验证，建议补充确认。"


def normalized_queries(candidate: dict[str, Any]) -> list[str]:
    values = candidate.get("query_terms") or [candidate.get("question_en")]
    result: list[str] = []
    for value in values:
        query = " ".join(str(value or "").split())
        if query and query not in result:
            result.append(query)
    return result


def short_excerpt(review: dict[str, Any], query: str, limit: int = 240) -> str:
    text = " ".join(str(review.get("评论内容") or review.get("评论标题") or "").replace("Search term:", "").split())
    sentences = re.split(r"(?<=[.!?])\s+", text)
    tokens = [token for token in re.findall(r"[a-z0-9]+", query.lower()) if len(token) > 2]
    best = max(sentences or [text], key=lambda value: sum(token in value.lower() for token in tokens))
    return best[:limit].strip() or text[:limit].strip()


def stable_id(candidate: dict[str, Any], query: str, source_asin: str, source_type: str, review_id: str) -> str:
    parts = [
        candidate["candidate_id"], candidate["original_keyword"], candidate["keyword_source"],
        query, source_asin, source_type, review_id,
    ]
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20].upper()
    return f"RAW-{digest}"


def assemble(asin: str, site: str, candidates_doc: dict[str, Any], reviews_doc: dict[str, Any]) -> dict[str, Any]:
    asin = asin.upper()
    if not ASIN_RE.fullmatch(asin):
        raise ValueError("invalid target ASIN")
    candidates = candidates_doc.get("candidates") or []
    if not candidates:
        raise ValueError("candidates must be non-empty")

    review_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    mappings: dict[tuple[str, str], list[dict[str, str]]] = {}
    for source_asin, state in (reviews_doc.get("asins") or {}).items():
        source_asin = source_asin.upper()
        for review in state.get("reviews") or []:
            review_lookup[(source_asin, str(review.get("评论ID") or ""))] = review
        for mapping in state.get("mappings") or []:
            key = (str(mapping.get("question_id") or ""), str(mapping.get("query") or ""))
            mappings.setdefault(key, []).append({
                "source_asin": source_asin,
                "review_id": str(mapping.get("评论ID") or ""),
                "query": str(mapping.get("query") or ""),
            })

    rows: list[dict[str, Any]] = []
    seen_candidate_ids: set[str] = set()
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id") or "")
        if not candidate_id or candidate_id in seen_candidate_ids:
            raise ValueError(f"candidate_id must be present and unique: {candidate_id!r}")
        seen_candidate_ids.add(candidate_id)
        for query in normalized_queries(candidate):
            hits = mappings.get((candidate_id, query), [])
            if not hits:
                source_type = "Listing事实" if candidate.get("keyword_source") == "Amazon Listing" else "关键词"
                rows.append(build_row(asin, site, candidate, query, asin, source_type, "无", None))
                continue
            for hit in hits:
                source_asin = hit["source_asin"]
                review_id = hit["review_id"]
                review = review_lookup.get((source_asin, review_id))
                if not review:
                    raise ValueError(f"missing review record for {source_asin}:{review_id}")
                source_type = "目标评论" if source_asin == asin else "竞品评论"
                rows.append(build_row(asin, site, candidate, query, source_asin, source_type, review_id, review))

    return {
        "asin": asin,
        "site": site.upper(),
        "seller_sprite_available": bool(candidates_doc.get("seller_sprite_available")),
        "max_questions": candidates_doc.get("max_questions", "unlimited"),
        "max_clean_questions": candidates_doc.get("max_clean_questions", "unlimited"),
        "rows": rows,
    }


def build_row(
    asin: str,
    site: str,
    candidate: dict[str, Any],
    query: str,
    source_asin: str,
    source_type: str,
    review_id: str,
    review: Optional[dict[str, Any]],
) -> dict[str, Any]:
    has_review = review is not None
    attribution = "目标商品" if source_type == "目标评论" else "竞品" if source_type == "竞品评论" else "无评论证据"
    excerpt = short_excerpt(review, query) if review else "0条评论证据"
    gap = str(candidate.get("data_gap") or "无")
    status = str(candidate.get("collection_status") or "已采集")
    if not has_review:
        status = f"{status}；0条评论证据" if "0条评论证据" not in status else status
    metric = str(candidate.get("seller_sprite_metric") or "未取得")
    listing_fact = str(candidate.get("listing_fact_basis") or "无")
    trace_value = excerpt if has_review else str(candidate.get("original_keyword") or listing_fact)
    row = {
        "记录ID": stable_id(candidate, query, source_asin, source_type, review_id),
        "目标ASIN": asin,
        "Amazon站点": site.upper(),
        "问题候选_EN": str(candidate.get("question_en") or ""),
        "问题候选_CN": str(candidate.get("question_cn") or ""),
        "答案候选_EN": str(candidate.get("answer_en") or FALLBACK_EN),
        "答案候选_CN": str(candidate.get("answer_cn") or FALLBACK_CN),
        "原始关键词": str(candidate.get("original_keyword") or ""),
        "关键词来源": str(candidate.get("keyword_source") or ""),
        "来源查询词": query,
        "意图初始标签": str(candidate.get("intent_initial_label") or "未分类"),
        "卖家精灵指标": metric,
        "来源ASIN": source_asin,
        "来源类型": source_type,
        "评论ID": review_id,
        "评论证据摘录": excerpt,
        "证据归属": attribution,
        "Listing事实依据": listing_fact,
        "数据冲突或缺口": gap,
        "采集状态": status,
        "candidate_id": candidate["candidate_id"],
        "trace_evidence": [{"kind": source_type, "value": trace_value}],
        "answer_evidence": candidate.get("answer_evidence") or [],
        "review_mapping": ({"query": query, "source_asin": source_asin, "review_id": review_id} if has_review else {}),
        "semantic_key": str(candidate.get("semantic_key") or ""),
        "decision_point": str(candidate.get("decision_point") or ""),
        "relevance_status": str(candidate.get("relevance_status") or "relevant"),
    }
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asin", required=True)
    parser.add_argument("--site", default="US")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--reviews", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    candidates = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    reviews = json.loads(Path(args.reviews).read_text(encoding="utf-8"))
    payload = assemble(args.asin, args.site, candidates, reviews)
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(Path(args.output).resolve()),
        "rows": len(payload["rows"]),
        "candidates": len({row["candidate_id"] for row in payload["rows"]}),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
