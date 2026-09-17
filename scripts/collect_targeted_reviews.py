#!/usr/bin/env python3
"""Adapter for targeted Rufus evidence using the existing 3.3 collector."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
from pathlib import Path
from typing import Any

DEFAULT_REVIEW_REPO = Path(r"C:\Users\Administrator\Desktop\Ecomtool工具[TOP]\2.3批量抓取竞品评论（测试）\amazon-rufus-review-collector")


def load_upstream(repo: Path) -> Any:
    source = repo / "scripts" / "amazon_reviews.py"
    if not source.exists():
        raise FileNotFoundError(f"3.3 collector not found: {source}")
    spec = importlib.util.spec_from_file_location("amazon_review_upstream", source)
    if not spec or not spec.loader:
        raise ImportError(f"cannot load 3.3 collector: {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_questions(path: Path) -> tuple[list[str], dict[str, list[str]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    records = (raw.get("candidates") or raw.get("questions")) if isinstance(raw, dict) else raw
    if not isinstance(records, list) or not records:
        raise ValueError("input must contain a non-empty candidates/questions list")
    ordered: list[str] = []
    query_to_questions: dict[str, list[str]] = {}
    for index, record in enumerate(records, 1):
        qid = str(record.get("candidate_id") or record.get("question_id") or f"Q{index:02d}")
        question = str(record.get("question_en") or "").strip()
        terms = [str(term).strip() for term in record.get("query_terms") or [] if str(term).strip()]
        if not question or not terms:
            raise ValueError(f"{qid}: question_en and at least one query term are required")
        for query in terms or [question]:
            key = " ".join(query.split())
            if key not in query_to_questions:
                ordered.append(key)
                query_to_questions[key] = []
            if qid not in query_to_questions[key]:
                query_to_questions[key].append(qid)
    return ordered, query_to_questions


def load_checkpoint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "asins": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1 or not isinstance(value.get("asins"), dict):
        raise ValueError("invalid targeted checkpoint")
    return value


async def collect(args: argparse.Namespace) -> dict[str, Any]:
    if args.site.upper() != "US":
        raise ValueError("targeted Rufus adapter currently supports site US")
    upstream = load_upstream(Path(args.review_repo))
    target = upstream.validate_asins([args.target_asin])[0]
    competitors = upstream.validate_asins(args.competitor_asins or []) if args.competitor_asins else []
    competitors = [asin for asin in competitors if asin != target]
    asins = [target, *competitors]
    queries, query_map = load_questions(Path(args.questions))
    workdir = Path(args.workdir).expanduser().resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = workdir / "targeted_checkpoint.json"
    checkpoint = load_checkpoint(checkpoint_path)

    from playwright.async_api import async_playwright

    profile_dir = Path(args.profile_dir or upstream.default_profile_dir()).expanduser().resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)
    launch: dict[str, Any] = {"headless": not args.headed}
    if args.browser == "chrome":
        launch["channel"] = "chrome"

    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(str(profile_dir), locale="en-US", **launch)

        async def route_handler(route: Any) -> None:
            if route.request.resource_type in {"image", "font", "media"}:
                await route.abort()
            else:
                await route.continue_()

        await context.route("**/*", route_handler)
        try:
            for asin in asins:
                saved = checkpoint["asins"].get(asin, {})
                if saved.get("status") == "complete":
                    continue
                completed = set(saved.get("completed_queries") or [])
                reviews = {row["评论ID"]: row for row in saved.get("reviews") or []}
                mappings = {
                    (m["question_id"], m["query"], m["评论ID"]): m
                    for m in saved.get("mappings") or []
                }
                page = await context.new_page()
                stop_reason = ""
                try:
                    response = await page.goto(upstream.RUFUS_START_URL, wait_until="domcontentloaded", timeout=args.timeout_ms)
                    stop_reason = upstream._rufus_stop_reason(response.status if response else 0, await page.content(), page.url)
                    for offset in range(0, len(queries), args.concurrency):
                        if stop_reason:
                            break
                        batch = [query for query in queries[offset:offset + args.concurrency] if query not in completed]
                        if not batch:
                            continue
                        responses = await asyncio.gather(*(
                            upstream._rufus_page_fetch(page, asin, query, args.timeout_ms) for query in batch
                        ))
                        for query, result in zip(batch, responses):
                            reason = upstream._rufus_stop_reason(
                                int(result.get("http_status") or 0), str(result.get("html") or ""), str(result.get("source_url") or "")
                            )
                            if reason:
                                stop_reason = stop_reason or reason
                                continue
                            rows = upstream.parse_rufus_html(
                                str(result.get("html") or ""), asin,
                                source_url=str(result.get("source_url") or ""), query=query,
                                capture_time=str(result.get("capture_time") or ""),
                                http_status=int(result.get("http_status") or 0), batch=offset // args.concurrency + 1,
                            )
                            for row in rows:
                                public = upstream._public_review(row)
                                reviews.setdefault(public["评论ID"], public)
                                for question_id in query_map[query]:
                                    mapping = {"question_id": question_id, "query": query, "下载ASIN": asin, "评论ID": public["评论ID"]}
                                    mappings[(question_id, query, public["评论ID"])] = mapping
                            completed.add(query)
                        state = {
                            "status": "blocked" if stop_reason else "running",
                            "stop_reason": upstream._public_reason(stop_reason),
                            "completed_queries": [q for q in queries if q in completed],
                            "reviews": list(reviews.values()),
                            "mappings": list(mappings.values()),
                        }
                        checkpoint["asins"][asin] = state
                        upstream.atomic_write_json(checkpoint_path, checkpoint)
                finally:
                    await page.close()
                state = checkpoint["asins"].setdefault(asin, {})
                state["status"] = "blocked" if stop_reason else "complete"
                state["stop_reason"] = upstream._public_reason(stop_reason)
                upstream.atomic_write_json(checkpoint_path, checkpoint)
                if stop_reason:
                    break
        finally:
            await context.close()

    result = {
        "target_asin": target,
        "competitor_asins": competitors,
        "coverage": "multi-query Amazon review sample; not all historical reviews",
        "asins": checkpoint["asins"],
    }
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-asin", required=True)
    parser.add_argument("--competitor-asins", nargs="*", default=[])
    parser.add_argument("--site", default="US")
    parser.add_argument("--questions", required=True)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--review-repo", default=str(DEFAULT_REVIEW_REPO))
    parser.add_argument("--browser", choices=("chromium", "chrome"), default="chrome")
    parser.add_argument("--profile-dir")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--concurrency", type=int, choices=range(1, 5), default=2)
    parser.add_argument("--timeout-ms", type=int, default=30000)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = asyncio.run(collect(args))
    blocked = any(state.get("status") == "blocked" for state in result["asins"].values())
    print(json.dumps({"status": "blocked" if blocked else "complete", "asins": list(result["asins"])}, ensure_ascii=False))
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
