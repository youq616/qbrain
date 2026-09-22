# N48G — Offline provider usage import into exact token accounting

2026-09-22. Status: approved after the separate plan review below.
Base main24dd3179c6f01f665a20ce65152d6e112ec6712c. The owner requests a complete
module and a separate coordinator self-review. N48E and N48F are already merged;
do not repeat their closure. No third-party or subagent review is claimed.

## Complete module

Add cost import before brain initialization. Accept one bounded JSON envelope
(schema qbrain-usage-import-v1, currency, explicit N48F rates, records). Each of up
to128 records has call_id, stage, rate_id, attempt, outcome, format and response.
Formats: openai_chat, openai_responses, anthropic_messages. These are named text-
token accounting contracts for complete non-stream response objects, not inferred
provider names or automatic network adapters. Null response is allowed only for
failure/unknown attempts and retains unknown usage. Output includes a directly
reusable qbrain-cost-input-v1, per-call mapping notes and the existing exact cost
report. Existing cost report and its arithmetic must stay byte-identical.

## Falsifiable acceptance

- OpenAI ordinary input = reported total input - cache-read - cache-write, with
  subset/total consistency checks. Anthropic input_tokens is already uncached;
  cache creation and reads are separate. Reasoning/prediction breakdowns must not
  be added to inclusive output again. Missing/null counts remain unknown rather
  than free; only mathematically proved zero can be inferred. Invalid quantities,
  impossible sums and mixed positive cache TTL writes refuse rather than guess.
- Reject stream chunks/events, nonterminal response objects, malformed structures,
  duplicate JSON keys (including ignored text objects), duplicate call IDs and
  repeated provider response identities. Same response attached to two retries is
  not silently billed twice. Failure records with usage are priced, not discarded.
- Rate-card provider/model must match an available response identity exactly when
  that card exists; missing cards remain unknown. No automatic price lookup, date/
  tier/TTL price guess, currency conversion, provider fee or invoice claim. Reject
  unsupported nonempty per-iteration accounting and positive audio modalities;
  explicitly note excluded server-tool fees. Unknown usage fields fail closed.
- Full response content is accepted as data but not copied into output, errors or
  hashes of normalized results. Only selected accounting values/opaque reference
  digests and caller metadata are emitted. This is not sanitization of user IDs or
  input files. Synthetic fixtures only in git; never real chats, keys or accounts.
- Enforce1MiB total input,262144 bytes per response,128 records,64 rate cards and
  N48F quantity/normalized-input/output limits. Strict one-document parsing and
  all-or-nothing output; preserve deterministic ordering and content-independent
  mapping. No writes, process spawn, network or environment reads.
- Actual direct C++ tests plus full-CLI tests on Windows and Linux: all3 adapters,
  cache partitions, unknown combinations, duplicates, malformed types, terminal
  status, unsafe advanced breakdowns, content sentinels, exact limits, repeatability
  and piping normalized output through unchanged cost report. Independent Python
  reference and negative-output mutations; retain N48F and original application,
  OpenCode and isolated-MCP regression gates. Separate review and sanitizer checks.

## Delivery and limits

Only a new pure accounting header, a cost-import early dispatcher and additive
standalone tests/workflow/docs. No DB schema, Hook, installer, existing test or
pricing arithmetic changes. Not live usage capture or model-effect evaluation.
Unknown/mixed billing cannot be made complete by inventing zero or extra calls.
Windows/native and merge status are claimed only when actually observed. Existing
N47X release/tag and Issue40 stay unchanged. If a platform write is blocked, stop
that write path and retain local delivery; no alternate-route circumvention.
