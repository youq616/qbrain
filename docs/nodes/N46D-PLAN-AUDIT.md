# N46D plan review

Reviewer: ChatGPT, continuing the owner-approved development workflow after the
explicitly disclosed N46C self-review. This is not Claude Code or an independent
external audit, and does not claim those services executed.
Verdict: PASS for scoped implementation; outcome pending.

- Priority: provider-controlled array growth and invalid batch association are
  correctness/resource/privacy defects upstream of retrieval improvements.
- Atomicity: parse into local temporary vectors; publish only after all fields
  pass. Check index sign/type/range BEFORE any cast or indexing.
- Resource safety: cap bytes, depth and parse events independently; returning
  false from a JSON callback is not rejection. Throw a private sentinel for
  depth/duplicate-key violations and return static, redacted error messages.
- Compatibility: preserve input-order output, configured model IDs, empty no-op,
  mock semantics and optional single-image index. Do not silently repair invalid
  provider output or normalize valid floats differently.
- Tests: combine pure malformed-input checks with real Windows transport and
  SQLite job persistence. The old adapter is explicitly test-only; repair its
  API/schema, not production policy. Add it to ongoing regression.
- Limits: documented application ceilings may reject previously accepted large
  batches or zero vectors. New parser budgets are not a process-RSS guarantee.
- Security: no model credentials or private data are needed; read failures cannot
  enable writes, external processing or paid retries.
- Ledger: implementation hardening, zero new operation names; add scoped delta.
- Rollback: code only. Actual native evidence required before completion.

P0: provider index overflow/allocation and partial batch acceptance must be closed.
P1: no raw exception echo; enforce image transport cap; do not regress old tests.
P2: model aliases/provenance and older already-stored embeddings remain separate;
Windows Server CI is not a logged-in Windows 11 Agent lifecycle acceptance.
