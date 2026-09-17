# Current-run source behavior

## Listing, search, and candidate generation

- Reuse the 1.1 product-page, Amazon autocomplete, and organic competitor collectors without modifying that repository.
- Consume only artifacts under the current ASIN run directory. Historical reports, template FAQs, and fallback product data are invalid inputs.
- Preserve Listing conflicts and answer with the narrowest target-supported claim.
- Generate questions from each current source record: source → buyer decision → natural question → query terms → semantic key. Wording helpers may expand as new decisions appear; they must not be a fixed question inventory.

## SellerSprite

- Use actual reverse-keyword, traffic, conversion, demand, review-analysis, and Listing-diagnosis values when available.
- Preserve every retrieved keyword row. Never synthesize search volume, rank, purchases, or conversion.
- If unavailable, continue with Amazon data and write `未取得`.
- Do not read, output, or save cookies, tokens, passwords, or browser credentials.

## Rufus reviews

- Reuse 3.3 persistent Chrome, `askSearch`, stop detection, parsing, checkpoint resume, and ASIN validation.
- Exact network queries may be fetched once and fanned back to every requesting candidate. This is transport deduplication, not Raw deduplication.
- Store reviews once per ASIN + review ID, but retain every candidate-query-review mapping.
- Results are multi-query samples, not the complete review history.

## Batch isolation

Use one temp directory, candidate file, checkpoint, review payload, and raw payload per ASIN. Validate every row's `目标ASIN` before cleaning or export. Shared wording rules are allowed; cached product facts, keywords, reviews, semantic keys, or answers are not.
