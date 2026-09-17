---
name: amazon-alexa-qa-builder
description: Collect source-preserving Amazon Alexa/Rufus Q&A candidates for one or more ASINs, then clean them into evidence-bounded final Q&A workbooks. Use when each ASIN needs both unlimited raw mappings and a semantically deduplicated Excel; do not use for general Listing rewrites.
---

# Amazon Alexa Q&A Builder

For each ASIN, deliver exactly two files: `{ASIN}_QA_Raw.xlsx` and `{ASIN}_QA_Clean.xlsx`. Process ASINs independently; inputting N ASINs produces 2N workbooks.

## Inputs

- Required: one or more ASINs matching `^[A-Z0-9]{10}$`. Default site: `US`.
- Optional: competitor ASINs, authenticated SellerSprite access, `max_questions`, and `max_clean_questions`.
- Both limits default to `unlimited`; apply a finite value only when the user explicitly supplies it.

## Sources

Treat these repositories as read-only and call them through adapters:

- Listing/search: `C:\Users\Administrator\Desktop\Ecomtool工具[TOP]\1.1流程\amazon-listing-optimizer-main`
- Reviews: `C:\Users\Administrator\Desktop\Ecomtool工具[TOP]\2.3批量抓取竞品评论（测试）\amazon-rufus-review-collector`

Read [references/source-flows.md](references/source-flows.md) before online collection. Read [references/data-contract.md](references/data-contract.md) before assembling or cleaning payloads.

## Per-ASIN workflow

1. Create an isolated temporary directory for the current ASIN. Use only current-run Listing facts, Amazon suggestions, SellerSprite rows, competitors, and reviews. Never load a prior ASIN's candidate or payload file.
2. Build one candidate per source record. Derive a natural US-English question, Chinese translation, short review queries, buyer decision point, and a `semantic_key` from that record. Rules may guide wording or intent labels, but must not supply a closed question catalog.
3. Preserve every candidate, repeated source, query, and review mapping in Raw. Do not deduplicate, rank-filter, or drop zero-review records. If competitors are absent, select 5–10 relevant organic products and exclude ads, accessories, wrong categories, and duplicate variants.
4. Run `collect_targeted_reviews.py` target-first, then competitors, with low concurrency and checkpoint resume. Competitor reviews prove buyer concern only.
5. Run `assemble_raw_payload.py`, `validate_payload.py`, then build `{ASIN}_QA_Raw.xlsx` with the single sheet `Q&A Raw Data`.
6. Read the complete raw payload. Mark irrelevant categories, brand pollution, accessory/wrong-product records, and obvious mojibake through `relevance_status`; assign the same `semantic_key` only to genuinely equivalent questions. Distinct purchase decisions under one intent keep distinct keys.
7. Run `clean_payload.py` and `validate_clean_payload.py`. Cleaning merges by semantic meaning, never by intent label or target count. Zero-review questions may remain when backed by a real keyword or Listing fact.
8. Build `{ASIN}_QA_Clean.xlsx` with the single sheet `Alexa Q&A`. Answers use target Listing facts or target-ASIN reviews only; otherwise use the exact bilingual fallback in the data contract.
9. Verify both workbooks reopen, have one sheet, frozen headers, filters, required columns, and no formula errors. Delete temporary JSON, checkpoints, screenshots, downloads, and logs after successful export.

## Batch export

Keep one raw payload per ASIN, then export all pairs in one command:

```powershell
python scripts\export_batch.py <temp>\ASIN1\raw_payload.json <temp>\ASIN2\raw_payload.json `
  --output-dir <output> --max-clean-questions unlimited `
  --node <node.exe> --node-modules <node_modules>
```

The output directory must contain only the requested 2N `.xlsx` files. Final responses report absolute paths, raw row counts, clean question counts, and validation status.
