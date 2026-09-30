# N48T follow-up: consistent bounded-summary coverage

2026-09-30. Base b82188181d96881d07093d101e7ae983ad041a40 /
0dc506c25d459f033a848f10bced1e8b682bd4f3. Owner requests recording the non-author PASS
and prioritizing the inherited256->257-page truncated-metadata edge if warranted.

## Scope and decision

Investigate the actual shared summary publication path, not another packaging or
verification-only module. Its digest covers the first256 selected page identities/
contents; directory coverage (partial) is stored separately. Equal selected digests
need not imply equal coverage when a model callback changes the257th matching page.
If reproduced, correct this before adding further optimization: a fresh cache must
not falsely describe a partial source as complete (or keep obsolete truncation).
The received b821 admission/transaction PASS remains valid for its original scope.

## Design review, before runtime modification

Reviewer: owner-authorized ChatGPT coordinator design self-review; not the external
reviewer. Verdict: approved to implement the narrow fix after exact-baseline repro.
Reject automatically calling the provider again (cost/permission side effects),
pretending the callback did not run, changing revision hashes/DB schema, silently
rewriting a returned model answer as a remedy, or refusing all large directories.

Use the already-required post-callback snapshot in the existing publish transaction.
Require equal selected signature, selected count and partial flag; otherwise return
existing evidence_changed before optional schema initialization/cache publication.
No additional query is required. The already-authorized callback is counted as1.
Changes beyond the selected prefix are allowed when selection AND coverage are
unchanged (e.g.257->258). Preserve original preflight, permissions, transaction
ownership, trigger policy, read locking and backup semantics. No source/SQL API change.
The validator is shared with PG; do not call SQLite tests a live PG verification.

## Falsifiable tests

1. Exact old source must demonstrate256->257 succeeds with stale partial=false;
   preserve stdout and native binary/source identities. Fixed source must refuse.
2. Cover both directions, warm/absent caches, soft delete/restore, namespace/source
   moves and same-connection plus actual separate SQLite writer callbacks. Check
   complete cache/DDL state after legitimate callback writes; no stale publication,
   no automatic retry, committed callback changes are not rolled back.
3. Positive controls: stable256, stable257,257->258, edits only beyond selected range,
   unrelated directory/source/namespace, and changes rolled back before callback end.
   Negative controls: selected-content mutation and255->256 (existing digest guard).
4. Retry only explicitly, with current evidence: correct truncated flag and cached
   fields, existing digest algorithm unchanged. Persisted legacy bad cache repair is
   not claimed: this fixes future publications, not a schema migration.
5. Re-run b821 preflight33/284 and original57 unchanged; native Windows/Linux workflow,
   original core/process regressions, local sanitizers. Use a new exact SHA. Do not
   call author's new tests the independent non-author PASS already received for b821.

## Ownership/rollback/remaining gates

Only shared context implementation, new regression target/test, N48T CI registration
and narrowly scoped documentation may change. Do not touch PR61/N48S six files,
packaging, defaults, fees, model accounts, main or merge/deployment actions. No new
runtime package. Rollback is the small publication predicate/test; schema unchanged.
The whole60/55-step release, real clients/models, signatures and other original
requirements remain separately tracked. No absolute defect-free claim.
