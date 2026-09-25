# N48H — Complete offline SSE usage import

2026-09-22. Approved after the separate plan review, before implementation.
Base main9c61049d29d9638b0b9558243025cb92a6d7e54d. The owner requests a complete
module and coordinator self-review. This is not a third-party or subagent review.

## Scope

Add native cost import-stream before ordinary brain initialization. Input is one
qbrain-stream-import-v1 envelope (currency, explicit N48F rates, records); each
record has call_id/stage/rate_id/attempt/outcome/format/stream. stream is the saved
UTF-8 SSE body, never a URL/path to fetch. Formats are openai_chat,
openai_responses and anthropic_messages. Up to32 streams,4MiB envelope,512KiB per
stream,256KiB per event and4096 data events per stream. Preserve the original
N48F/G code and tests byte-for-byte. Output reuses cost_input/cost_report/mapping
and adds bounded body-free stream validation observations.

## Falsifiable acceptance

1. Parse CR/LF/CRLF, optional leading BOM, comments, multiline data and blank-line
   event termination. Reject unfinished final blocks, ambiguous duplicate named
   fields, unsupported SSE fields, invalid UTF-8/NUL, malformed or duplicate-key
   JSON anywhere (including ignored content). These are strict replay policies,
   not a universal EventSource implementation or live network client.
2. Chat requires consistent response ID/model, bounded distinct choice indices,
   completed choices, at most one final empty-choices usage chunk, and one [DONE]
   terminator. No data may follow it. A valid ended stream without usage remains
   unknown, not free. No summing token-sized content chunks.
3. Responses requires response.created first, contiguous sequence numbers from0,
   one consistent response identity and one completed/failed/incomplete terminal
   event. Use terminal usage once, never sum intermediate response snapshots.
   Reject replayed/resumed fragments, sequence gaps and errors without a final
   response. Accept only the documented text/reasoning/function-output event
   subset; this is accounting validation, not full output-content reconstruction.
4. Anthropic requires message_start, balanced indexed content blocks, cumulative
   message_delta usage and message_stop. Cumulative updates replace/merge fields,
   never add earlier totals again; observed counters may not decrease. An initial
   output count alone is not final usage. Unknowns remain unknown. Refuse model
   fallback/unsupported blocks and error/truncated streams rather than bill a
   partial snapshot as a complete response. Keep N48G TTL/audio/iteration rules.
5. Exact IDs/model/rates, unknown propagation, original amount overflow checks,
   duplicate response/call rejection and failure usage semantics are inherited.
   No raw content, stream hash or tool argument appears in results/errors. Metadata
   supplied by callers is not automatically anonymous. Token cost remains distinct
   from invoice/fees/discounts and from proof of all requests or model consumption.
6. Direct C++ and real CLI tests on Windows/Linux cover three protocols, final vs
   cumulative usage, every terminal/ordering failure, byte/event/record bounds,
   missing/null counts, malformed ignored data, content independence, unknown
   pricing, duplicates across streams and exact piping into unchanged cost report.
   Independent reference cases and failure mutations must not reuse product event
   reconstruction. Run sanitizers and retain existing N48F/G, OpenCode, MCP,
   original full60 Windows and portable core/process gates without weakened tests.

## Delivery and rollback

Add one pure header, early CLI dispatch, standalone tests and dedicated workflow.
No DB/storage change, process spawn, network, key/environment reads, provider
request or automatic collection. No raw real conversations in git. Partial/error
SSE captures are rejected atomically; an operator may record an unknown failed
attempt via existing cost import, never silently drop it from a real ledger.
Remove additive route/header to roll back. No current Release/tag is replaced.
Known-body limits and closed event contracts are explicit compatibility limits,
not arbitrary-provider support. Issue40, actual quality/consumption, PG and signing
remain independent unclosed gates. Do not bypass a blocked repository write.

## Acceptance closure — 2026-09-25

Status: **done for the bounded source module** after the owner-authorized separate
outcome review in N48H-HARD-AUDIT.md and fixed-candidate native qualification.
Qualified commit0227db92 / tree9b95184a integrates repaired817d222a without replacing
its product. The earlier implementation amendment permits Responses origin0 or1
followed by strict continuity; the original “from0” sentence above is preserved as
plan history, not misreported as the final contract. No live collection, actual
model consumption, release/signing, PG parity or Issue40 closure is inferred.
