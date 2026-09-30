# PR62 R1 — SQLite admission before evidence/provider use

2026-09-30. Repair base147b270898f57d81614eebd8bfd1dc3828711ddb,
tree3c835faa890f1815d4289906cfb84df2bb1489e5. Independent reviewer reported that replacing
ctx_page_insert with AFTER INSERT/SELECT1 yields context_schema_incomplete only after
one synthetic provider call. Expected calls=0. The original57 tests do not cover this.
Any earlier statement that this published head was already repaired or passed425 checks
is withdrawn as evidence for this blocker. No unpushed code is treated as a delivered fix.

## Repair design review before implementation

Owner explicitly requests this repair and a new fixed-SHA independent outcome review.
Engineering design: accepted for implementation, not a non-author outcome PASS.
1. An owned SQLite read snapshot refuses existing caller transactions, checks the
   relevant TEMP-name namespace and validates the complete optional-cache policy before
   parse/source/config/page evidence reads. Missing cache is valid and does not initialize.
2. Both context read and summary use it. Release it before any provider callback.
3. After the callback, refuse caller-owned transactions and recheck the namespace/policy
   before backup/publication. Keep in-transaction evidence/consent/policy revalidation.
4. Preserve the existing57 tests and add a separate preflight suite: the exact repro;
   malformed/missing/mixed schema; TEMP shadowing; caller BEGIN/IMMEDIATE/SAVEPOINT;
   positive callbacks for valid absent/legacy/scoped caches; late tampering and callback
   transaction ownership. A valid request followed by concurrent mutation may have one
   provider call and must refuse publication; do not pretend a past call can be undone.

No new permission, timeout relaxation, default network request, schema version or
PostgreSQL policy. SQLite BEGIN is an application-owned read scope, not an engine-enforced
READ ONLY transaction or a sandbox against malicious SQL owners. No N48S file dependency.

## Acceptance still required

Reproduce the old failure on pinned source; publish the repair atomically with its new
regression; confirm exact remote blobs/tree; execute fresh Windows/Linux native workflow;
retain failures; request/review non-author outcome against the actual new SHA. No merge,
deployment, package rewrite or project-completion claim. Self-checks are not non-author
review. N48S PR61 head4fb5f7bcc4d5871b7eef409963806ba58b486ae1 and its six files are excluded.

## Follow-up found before final acceptance

A separate probe of25d499730bcfe819ae545a84b436b37fc689f73e found that SQLite can hold
an implicit INSERT/RETURNING writer while get_autocommit is1. The old facade's explicit
transaction predicate returned false; the owned BEGIN/ROLLBACK adopted that transaction,
called the synthetic provider once and removed both pending caller rows. Thus25d is not
accepted even if its then-current CI passes. The observed failure is retained.

Design amendment: add a separate storage-facade transaction_pending() predicate using
both autocommit and sqlite3_txn_state across all SQLite databases; keep the existing
transaction_active() semantics unchanged for other callers/backends. Context admission
uses the stronger predicate. Extend regression with pending reads/writers/attached
writers, an idle prepared-statement positive control and a callback-created pending
writer. All applicable tests/CI must bind to the new final SHA, not25d. No N48S change.
