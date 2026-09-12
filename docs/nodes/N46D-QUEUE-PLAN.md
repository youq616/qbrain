# N46D queue repair — approved engineering plan

Owner authorization (September 12, 2026): “好的，继续修复。你不需要遵循原来本地规定，不需要外部审核，你自己做独立审核就可以接受。”
Reviewer: ChatGPT, separate engineering review pass by the implementer; not an
independent third-party or Claude Code audit. The owner explicitly replaces that
external-review prerequisite. No security, consent or evidence gate is waived.

Baseline PR #9 head a35313697be95064a99457a131412ec0ec675111; runtime 6f88c073.
Scope: QB-QUEUE-001..004 and their duplicate generic worker path in Windows Qbrain.

## Design and falsifiable acceptance

- Both automatic and generic embedding workers use one implementation. Claim
  jobs atomically using the existing lease mechanism. Fence every persistence
  and terminal update on job id, attempt, token, active status and live lease.
- Batch within 2048 inputs, configured/worst-case vector element and JSON byte
  limits. Do not remove N46D parser limits. Query only bounded batches of pending
  chunks; validate UTF-8 and exact JSON-escaped sizes before provider processing.
- Read a live page/chunk-set snapshot. Recheck before every outbound batch and
  in a short write transaction before applying the response. Compare page/source,
  content revision, chunk-set ids/count, and exact per-chunk text/index. Check
  actual affected rows. Never hold a transaction during provider I/O.
- Deleted/missing targets are cancelled without dispatch when already deleted;
  late results are discarded. Changed/rechunked targets fail as stale and require
  explicit retry. Completed batches stay committed if a later batch fails. Each
  batch and its job progress commit together; current-batch failures roll back.
- Per-job chunks counts are actual writes, not invocation totals. Completion is
  recorded atomically after liveness, ownership and remaining-work checks.
- Test both entry points, 2049 inputs, delete/rechunk before and during dispatch,
  partial provider failure + retry, cancellation/pause/expired/reassigned lease,
  two SQLite connections, overlapping workers, and injected write failures.
- Retain N46D/N46C and full native Windows suites; no old package certifies changes.

Limits: no exactly-once billing promise on crash/lease expiry, no retroactive
recall of already transmitted inputs, no page-scoped distributed claim deduplication
across distinct jobs, no new schema/model repair/paid calls. PostgreSQL locking
is implemented via its existing backend but not certified without real PG tests.
Rollback is code-only; no migrations. No unrelated repository changes.

## Plan review

Verdict: PASS for scoped implementation under the explicit owner authorization.
P1 gates: preserve parser caps; both workers; conditional current-batch atomicity;
no outbound call for already-deleted page; no stale success or stale-token write.
P2 limits are listed above. Outcome remains pending actual tests.
