# N47A engineering plan review

Reviewer: ChatGPT under the owner's explicit override. Separate design review,
not independent third-party/Claude Code review. Verdict: PASS for implementation;
actual output/native acceptance pending. Reviewed before production edits.

- Existing facts name conflict is resolved by a separate additive module, not a
  destructive replacement. Lazy initialization means normal read/startup is not
  permission to migrate every brain. On-disk backup must succeed first.
- Complete quotes rather than guessed triples preserve negation and context.
  Caller predicates are annotations, not model-verified truths. No arbitrary 0.8
  confidence number is introduced. User role itself is caller attestation.
- Evidence must be revalidated on reads and inside write transactions; snapshots
  bind quotes to source/event/item identity. Hashes do not defeat a malicious
  actor who can rewrite the whole database, nor replace MCP authorization.
- Privacy takes precedence over historical-version retention: final evidence
  deletion removes copied fact text. Use schema triggers so existing forget paths
  and older binaries do not require a new C++ callback to clean new tables.
- Explicit supersession is optimistic and atomic; no automatic conflict guesses,
  no revival after evidence deletion, no cross-source edges or privilege growth.
- Reuse existing memory tool gates with strict action-specific inputs; no new
  broad tool or automatic recall injection. All read budgets remain bounded.
- Test actual production classes, storage and CLI/MCP, including failing writes,
  concurrency and old-data compatibility. Preserve exact registry/package gates.

P0 design blockers: none identified after the naming/privacy adjustments.
P1 implementation gates: no unsupported claims after evidence loss, no partial
fact/evidence/relation writes, proper source/write gating, native regression.
P2: semantic inference, freshness scoring, audit signing, full ACL/DLP and PG
fact parity not claimed. Same-connection concurrent use is unsupported; use
separate Brain/Database connections per thread. No new required runtime service.

Design references consulted:
https://www.sqlite.org/foreignkeys.html
https://www.sqlite.org/lang_transaction.html
https://www.sqlite.org/backup.html
