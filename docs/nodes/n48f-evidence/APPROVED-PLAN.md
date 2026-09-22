# N48F — Offline whole-pipeline usage and cost accounting

2026-09-22. Status: approved after the separate plan review below.
Base main:6c4f779ee752bd4043847eb79a6d1a5e694d024e. Owner requests one complete module and a separate coordinator outcome review.

## Scope

Implement a native `qbrain cost report` command dispatched before default-brain initialization. Read one strictly bounded JSON document from stdin. It contains a single currency, explicit user-supplied rate cards and up to512 unique invocation records across main/embedding/summary/extraction/rerank/other stages. Repeated attempts have distinct call IDs and an explicit attempt number. All recorded attempts, including failed calls, remain visible; no inferred free retries.

Use normalized, mutually exclusive token buckets: input_uncached, input_cache_read, input_cache_write, output. Token counts and rates may be null. Rates are decimal strings in currency per million tokens, at most six fractional digits, never floating point. Exact integer multiplication produces twelve-decimal currency strings; checked arithmetic rejects overflow. Rate cards have explicit IDs, so callers can separate cache TTLs, provider tiers or historical price schedules without guessing current vendor prices.

Return per-call component costs, per-stage totals, per-rate totals and overall totals. Return a known subtotal plus missing-component reasons; a complete estimate is null whenever any component is unknown. Zero tokens with an unknown rate have known zero cost; unknown tokens remain unknown even at a zero rate. No absent or missing usage is silently changed into zero. Output names the currency but performs no conversion or pricing lookup. The estimate is arithmetic on caller-supplied records, not an authenticated invoice, proof of complete request capture or observed provider billing.

## Falsifiable acceptance

1. Strict unique-key JSON, exact allowed fields, safe bounded identifiers, one ISO-style uppercase three-letter currency label, integer/null token counts, decimal-string/null rates. Reject duplicate call/rate IDs, negatives, floating quantities, excessive digits/rates/tokens and unknown fields. Limits:256KiB input,512 calls,64 rate cards; bounded output and checked unsigned arithmetic.
2. Stable input-order-independent output and canonical input digest; unchanged rates/usage produce identical results. Per-call sums reconcile to stage/rate and overall totals without rounding drift. Duplicated invocation IDs reject, never count twice.
3. Missing usage, missing rate card or partly unpriced usage yields explicit null total, identified gaps and a separately labelled known subtotal. Known zero costs and exact fractional values retain their distinction from unknown. Failed attempts with reported usage are counted, not dropped.
4. No network, secret lookup, provider SDK, database open, persistent file write or subprocess launch. Explicit stdin only. No prompt/response body fields accepted. Reports may contain user-provided safe IDs; not a claim that arbitrary inputs are anonymized.
5. Add independent decimal-reference and permutation/aggregation tests; CLI boundary/UTF-8/duplicate-key/byte limits; full maximum input and arithmetic overflow; no filesystem mutation in isolated HOME; preserve original runtime and fourteen process suites. Compile actual Windows native plus Linux and retain original Windows full60 and Linux core/batch tests, not substitutes for the new independent target.
6. Separate outcome review checks input semantics, unsigned overflow, unknown propagation, privacy, exact arithmetic and actual original artifacts. Fix findings and re-run changed source before claiming complete acceptance. Do not infer native Windows or real provider results from Linux/synthetic tests.

## Plan review — separate engineering pass

Reviewer: coordinating ChatGPT under the user's current explicit self-review authorization, not another subagent or third party. Verdict: APPROVED. No blocking plan finding within this bounded offline scope.

This implements the route's missing calculable whole-pipeline cost layer without making up prices or fee observations. Vendor token fields are not interchangeable: Claude input excludes cache read/write, while other APIs may include cached input in total input. Require disjoint normalized buckets, explicit nulls and caller-selected rate IDs rather than accepting raw mixed vendor schemas. Official Claude prompt-caching documentation was checked for this distinction. Separate TTL/tier charges must use separate rate IDs; omitted provider-specific fees/taxes/discounts are outside this token-only estimate and must not be silently claimed included.

Integer fixed-point arithmetic avoids binary floating error; multiplication and every aggregate addition must be overflow-checked. Use a conservative representable range and reject excessive totals instead of wrapping. Explicit output completeness means only supplied token components are priced, not that the whole invoice or all calls were captured. Data parsing and final report assembly must complete before any stdout success output.

Rollback is removal of the additive module and early CLI dispatch. No schema migration or permission change. Old report formats, model tools, MCP names, ledger inventory and public releases stay untouched; record a node delta only. Issue40, real model consumption/quality/cost, PG and signing gates stay open.