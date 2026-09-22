# N48G outcome review — provider usage import and exact token accounting

2026-09-22, Asia/Seoul. PASS for the approved offline source-module scope.
No known unresolved blocking finding remains within that scope. This is not a
zero-defect, provider-billing, model-utility, live-client or stable-release guarantee.
Reviewer: coordinating ChatGPT, in a separate engineering pass requested by the
owner; not a subagent or third-party certification.

## Fixed objects and continuation

Base main24dd3179c6f01f665a20ce65152d6e112ec6712c.
Plan/review38613f33b763f976b5d1bfe44668e440198835da preceded implementation.
Accepted source4182ba4262e223ad3378f7cd26318347cfe0efa0;
accepted tree783cfefd3db816ac8a4fde1ff72e9404a3bccfe8.
Fixed push/attempt1 run35708615695: Windows106683489207 and portable106683488918,
all required steps completed/success and individually checked.

This continuation found N48E/N48F already merged and PR48 already implementing
N48G. It did not repeat their earlier local-only delivery or create a duplicate
module. It inspected the actual plan, code, native artifacts and existing findings,
then added independently generated input/reference tests and usable examples.
No candidate production change was necessary in this final review. The original
plan is preserved byte-for-byte under n48g-evidence/APPROVED-PLAN.md.

## Approved gates and evidence

| Gate | Reviewed behavior and actual evidence |
| --- | --- |
| Complete import pipeline | Native cost import accepts the explicitly selected Chat, Responses or Messages final non-stream object, returns normalized cost_input and the unchanged N48F cost_report. Three native round-trip pipelines match cost report exactly. |
| No cached-token double billing | OpenAI uncached input is inclusive input minus known cache-read/write; Anthropic input is already separate. Output detail is validated as a subset, not added again. All three adapters and generated known/null/missing/zero combinations pass independent comparisons. |
| Unknown is not free | Missing usage/rates remain null; known subtotal is retained separately. An explicit zero input can prove both OpenAI cache buckets zero. Invalid totals/lower bounds refuse instead of filling unknown quantities. |
| Refuse ambiguous accounting | Duplicate call IDs and same-provider response IDs within a batch reject; nonterminal/stream shapes, conflicting totals, unknown usage fields, mixed positive cache TTLs, positive audio or nonempty iteration breakdowns refuse. No automatic rate lookup or repair. |
| Privacy and authority | No brain initialization, files, credentials, network or provider request. Input content is not emitted or included in normalized hashes; IDs and user-supplied labels are not claimed to be anonymized. Duplicate keys are rejected even in otherwise ignored content. |
| Preserve existing behavior | Existing N48F arithmetic/tests are byte-identical. New early main dispatch and a pure header are the only production changes. Original Windows60, Linux6 core/batch, OpenCode lifecycle, N48D172 and14 retained process suites pass. |
| Independent outcome review | Raw source/binary/test identity and complete saved streams reread; additional768 generated state combinations, mixed-batch invariance, Fraction results, content-invariance and refusal checks pass. Local ASan/UBSan direct tests also pass. |

Git comparison confirms only main.cpp changes among inherited production files;
provider_usage.hpp and dedicated tests/workflow are additions. No schema, Hook,
installer, MCP permission, canonical inventory or original cost arithmetic changes.

## Earlier findings, preserved rather than relabelled

LOWER-BOUND-REVIEW.md records that an earlier local candidate accepted impossible
known-cache or reasoning lower bounds when a parent counter was unknown. Its
approved repair checks the total against independently known lower bounds without
inventing missing usage. TOOL-COUNT-REVIEW.md records an early exit after a tool-fee
warning that skipped a later invalid tool count; final code validates every count.
The accepted native tests contain both corrections. This final pass reran their
negative conditions but did not reconstruct or claim a new run of those old binaries.

This pass initially used the wrong archive member name in the local extraction
helper, and then supplied the Windows-only flag to a portable semantic validator.
Both local evidence-adapter mistakes were corrected to the actual member and
platform contracts. Product and original test assertions were not changed.

## Native artifacts and original record replay

Original ZIPs downloaded and checked against live GitHub IDs/size/SHA256, CRCs,
member paths and exact source markers:

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| portable10685559260 |20539967|4e3f3414d19149f587f93cf9f424691aafead806c63544ebbd46352750ddddee|
| windows10686901021 |19498868|8fe7372280d61f5f3168ae714da3977e7481471dab04fb046d01cdaa80f36d11|

1330 canonical source files reconstruct the accepted Git tree. Windows has identical
members and modes;1316 files differ solely by exact LF-to-CRLF conversion. Actual
EXE hashes are Linux8a74254af41cbeca07405bf4efa6c3f0495ae5e7092dcffc328cd3b7b7e94649 and
Windows782c9faa7712a666d35ee781977a41f4ed639db0948f29bad82585e76fbe6763.

Each platform:59 new direct checks; each Python mode231 checks,230 calls and690
saved stdin/stdout/stderr streams, comprising176 successful imports,51 refusals
and3 normalized-cost pipelines. Source-owned independent partition/Decimal replay
and12 output mutations were rerun against all four reports with matching bytes.
N48F direct103 and per-mode149/148/444 records were likewise independently replayed.

All16 lifecycle-driver and18 retained-driver entries have exit0 and matching raw
output/log hashes. Original lifecycle reports, batch/integrity/page raw streams,
fact/multiterm/Hook/lifecycle semantic validators and N48D probe reports were rerun.
Original context65 has summary evidence, not per-command raw bodies; none were
invented. Windows BUILD_OK and60 original registered groups are present; Linux6
original core/batch targets and4 lifecycle targets passed. Real PG remains SKIP-PG.
Normal and optimized Python readback produce identical20085-byte summaries.

## Additional tests executed in this pass

review_import_reference.py generates four independent counter states (missing,
null, zero, positive) over all four buckets for each of three formats:768 cases.
It also tests12 mixed16-call batches and their shuffled forms, content-independent
normalization, exact cost report pipelines, duplicate response refusal, tool-counter
validation, ignored-content duplicate keys and known lower-bound contradictions.
Expected token partitions are generated without the product importer/test mapper;
full monetary results use the separately SHA-pinned N48F Fraction oracle.

On the exact downloaded Linux product, normal and optimized Python each execute
824 calls,2472 raw streams and6524 assertions. Both deterministic review records
are byte-identical. These are repeated assertions over generated scenarios, not
thousands of distinct product features. The original231 checks and downloaded
59/103 direct binaries were rerun. A newly compiled unchanged59-check direct test
passed Clang ASan/UBSan with leak checking and empty diagnostic stderr. No new full
product build, local Windows execution or actual provider response is claimed.

The three-format example uses explicitly invented prices. It was executed against
the downloaded product and yields token total0.000729000000 USD. This demonstrates
arithmetic, not a quotation of current provider prices. Exact records/hashes are in
SUMMARY.json; the repository retains reproducible code and derived pins, not all
raw native archives or local supplemental streams.

## Operational limits and merge boundary

OpenAI caching documentation and Chat usage reference were checked on2026-09-22:
https://developers.openai.com/api/docs/guides/prompt-caching and
https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create .
Anthropic's separate ordinary/cache counters were checked against
https://platform.claude.com/docs/en/api/rate-limits and the Messages reference.
The importer implements named bounded contracts, not automatic adaptation to every
past/future provider, model, gateway, currency, cache TTL or billing tier.

Older responses omitting cache_write_tokens intentionally remain incomplete unless
zero is proved; do not insert fabricated zeros to make the report green. Non-token
fees/taxes/discounts are excluded even when known token components are complete.
Deduplication is within one input, not across separate invocations. Response IDs,
rate cards and supplied outcome labels are not provider-authenticated. A hash is
not a signature, collection-completeness proof or private-data sanitization.

No release/tag is changed. Public N47X lacks later N47Y/N47Z/N48D/N48E/N48F/N48G
source additions. Live usage collection, actual memory consumption, model quality/
fees, Issue40, PG and signing remain separate gates. Final changes may contain
only docs/examples and already-executed review material over4182. Compare their
diff and actual merge tree; do not predeclare newly triggered CI successful.
Original Actions retention expires2026-10-06, not permanent storage.
