# N48J — N47S execution-to-cost bridge

2026-09-26. Base main 3c944a9df0ca1867ff3b320a20f4a3632c92ff0f,
tree f162c1ce07af8c869a9a8bb7312afa6bfbf74307. Owner requested a complete module
and the coordinator's own separate post-implementation review.

## Contract and deliberate scope

Add optional offline evaluation tool tools/acceptance/model_cost.py, with export
and verify subcommands. Read an existing N47S v2 plan / v1 execution directory;
validate exact schedule, immutable request bytes, started/finished receipts,
response hashes and parsed response metadata. Do not require or read the answer
key, invoke the HTTP executor, read credentials, change native runtime or score
model quality. Only caller-selected files and the explicit qbrain executable are
used. Raw prompt/answer/endpoint text is never copied into exported reports.

Input price document: qbrain-model-cost-rates-v1, currency, rates, and required
scope=scheduled_main_requests_only. This is deliberately NOT full-pipeline cost
accounting: engine preparation, summarization and other outside calls are not
observed. Rate cards match exact reported OpenAI-wire model IDs, no guessed aliases
or prices. Missing cards/counts remain unknown. Unsupported/contradictory reported
usage is rejected by the unchanged N48G native importer, not silently repaired.

Project validated terminal Chat fields only (id/model/object/usage/finish reasons)
into existing cost import. Preserve raw usage including cache details, never
reconstruct it from the receipt's lossy aggregate counts. Nonterminal/absent or
redacted failed responses become explicit unknown attempted calls. Retain usable
terminal usage of failed answers. Reject duplicate response IDs across both arms.
Not-attempted rows are coverage observations, not fabricated provider calls.
Missing run.json (hard crash) is rejected; no automatic recovery/retry is implied.

Build a complete 50-task comparison only when every planned request was actually
attempted. Any failed row conservatively withholds deltas through ledger_complete.
With fewer attempts emit both partial ledgers/reports, all 100 coverage observations,
and comparison=null. Bind common conditions and each task to the SAME plan and
source packet pair, not to different treatment request bytes. Native N48I determines
numeric eligibility; it does not imply quality, live models or complete egress.

## Safety and falsifiable gates

1. Strict JSON duplicate keys/types/depth, bounded sizes and exact field/file
   inventories. Deny symlinks/reparse points/nonregular inputs; no caller-controlled
   relative paths from receipts. Re-read source/binary before publishing. Document
   that this is not a hostile concurrent-filesystem or arbitrary-executable sandbox.
2. Validate source first, calculate with unchanged native import/report/compare,
   then publish only to a new external output directory. No overwrite of source,
   existing output, permissions, keys or brain. Manifest written last; partial I/O
   output is nonaccepted evidence, never reported as a completed bundle.
3. Deterministic body-free report, exact provenance hashes, ledgers, and optional
   comparison input. Verify regenerates from original run/rates/binary and compares
   exact bytes and inventories; a self-edited bundle manifest cannot authenticate it.
4. Tests cover 100 completed requests, missing cache usage/rates, reported-model
   drift, all failure classes, known failed usage, truncation/nonattempted coverage,
   cross-arm duplicates, receipt/count/request/response changes, JSON/size/path
   bounds, readback mutations, no-overwrite and no-network/no-key behavior.
5. Execute a real loopback HTTP pipeline with unique response IDs and complete
   synthetic usage using the UNCHANGED N47S executor, then bridge with actual native
   binary and compare exact arithmetic. No loopback answer is a real model result.
6. Run all retained acceptance-tool suites and native cost/import/comparison/stream
   regressions. Fresh Windows/Linux CI must execute the exact submitted new tool;
   no product sources or old tests/workflows may change. Separate review after
   implementation must record actual findings, executed results and limitations.

Delivery includes source, tests, reproducible examples and separate review evidence.
Use normal branch/expected-head writes, never overwrite parallel work. No installer,
Release/tag, PG, signing, real-client consumption or Issue40 closure from this module.

## Acceptance closure — 2026-09-26

Done for the bounded source module at bb5ea5fe / tree96f148ab after actual native
Windows/Linux qualification, original artifact readback and the separate outcome
review in N48J-HARD-AUDIT.md. This does not certify provider invoices, real model
quality, full pipeline costs or signed-in host consumption. Closing changes are
documentation/history/executed evidence only; actual merge identity is in PR51.
