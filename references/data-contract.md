# Q&A data and evidence contract

## Candidate input

`candidates.json` contains `seller_sprite_available`, `max_questions`, `max_clean_questions`, and a `candidates` array. Both limits default to `unlimited`.

Every source record remains separate and has a stable `candidate_id`, natural bilingual question, original keyword/fact, keyword source, short query terms, initial intent, actual SellerSprite metrics or `未取得`, Listing basis, answer candidate, and `answer_evidence`.

Cleaning metadata is current-product-specific:

- `decision_point`: the concrete buying decision, such as fragrance, lick safety, or antibacterial claim.
- `semantic_key`: a normalized meaning key. Equivalent wording shares a key; merely sharing an intent does not.
- `relevance_status`: `relevant` by default; use `irrelevant`, `brand_pollution`, `wrong_product`, `accessory`, or `garbled` only from current-ASIN evidence.

Allowed keyword sources are `Amazon Listing`, `Amazon联想词`, and `卖家精灵`.

## Raw output

One row is emitted for every candidate-query-review mapping. A query with no hit keeps one `0条评论证据` row. Repeated questions, sources, keywords, ASINs, and reviews are never merged.

Workbook columns, in order:

`记录ID, 目标ASIN, Amazon站点, 问题候选_EN, 问题候选_CN, 答案候选_EN, 答案候选_CN, 原始关键词, 关键词来源, 来源查询词, 意图初始标签, 卖家精灵指标, 来源ASIN, 来源类型, 评论ID, 评论证据摘录, 证据归属, Listing事实依据, 数据冲突或缺口, 采集状态`

Internal fields include `candidate_id`, `semantic_key`, `decision_point`, `relevance_status`, `trace_evidence`, `answer_evidence`, and `review_mapping`.

## Clean output

The cleaner reads every raw row, removes only records explicitly identified as pollution/garble, and groups by `semantic_key`. With no key, exact normalized question text is the conservative fallback. It never applies a per-intent quota or a default Top-N.

Workbook columns, in order:

`序号, 优先级, Alexa问题_EN, Alexa问题_CN, 标准答案_EN, 标准答案_CN, 意图分类, 核心关键词, 关键词来源, 卖家精灵指标, Listing覆盖状态, 目标ASIN评论证据数, 竞品评论证据数, 评论证据摘要, 证据ASIN, 数据冲突或缺口, 置信度, 建议动作`

`max_clean_questions` defaults to `unlimited`. A positive integer is honored only when explicitly requested.

## Answer boundary

A positive/descriptive answer needs nonempty `product_fact` or `target_review` evidence whose `source_asin` equals the target ASIN. Competitor reviews cannot prove a target feature. Without target support, use exactly:

- `Not verified from the current product information.`
- `当前商品资料未验证，建议补充确认。`

Raw and Clean validators reject target-ASIN mismatches and unsupported affirmative answers.
