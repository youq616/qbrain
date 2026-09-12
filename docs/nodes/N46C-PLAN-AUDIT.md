# N46C plan assessment

Assessor: ChatGPT under the continued owner-approved development workflow
recorded in issue #2 and the N46B delivery. Not Claude Code or an independent
external audit. Reviewed before implementation.

Verdict: PASS for implementation, with native outcome evidence still required.

- Scope and stack: only native Windows Qbrain retrieval, no required service.
- Exactness: a discarded page's old score cannot regain relevance because the
  K-th threshold only improves; a later better chunk can re-enter. Deterministic
  page identity breaks inter-page ties, and best snippet breaks same-page ties.
  Eviction/re-entry and order permutations require independent oracle tests.
- Privacy: do not add a persistent result/embedding cache in this node. Keep
  source filters and live deleted-row exclusion. Counts bind both source and
  slug; a slug-only batch would be a blocking correctness defect.
- Resources: only retained candidates have the K bound. Input blobs, backend
  buffering, SQLite caches and allocator RSS are explicitly outside this claim.
- Testability: differential oracle, native SQLite trace, mutation tests,
  baseline timing and exact group-log/package gates are concrete acceptance.
- Ledger: no new operations; add a performance delta, not broad parity claims.
- Rollback: code-only; no database format change or data deletion.

P0: none identified in this bounded design.
P1 gates to resolve in implementation: snippet tie preservation after eviction;
source-scoped batch equivalence; no silent scan truncation; same-source evidence.
P2: scan remains linear in embedded chunks; model provenance filtering, ANN,
real-provider task quality and PostgreSQL buffering need independent evaluation.
