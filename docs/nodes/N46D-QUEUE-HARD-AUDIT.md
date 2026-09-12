# N46D queue repairs — engineering outcome review

Verdict: **PASS for this scoped N46D implementation and evidence**. Reviewer:
ChatGPT, performing separate plan and outcome engineering passes after the owner
explicitly removed the external-auditor prerequisite on September 12, 2026.
This is not independent third-party or Claude Code review. The exact authorization
is preserved in AGENTS.md and N46D-QUEUE-PLAN.md.

## Provenance

Tested source `464045e2451ec71ca37dd8e92bcf4ac0d9325a0b`; source tree `15b5f46daf7d125dc19b9b34dffed05f0df77253`.
[Development validation](https://github.com/youq616/qbrain/actions/runs/34682889565)
and [N42 validation](https://github.com/youq616/qbrain/actions/runs/34682889570)
completed successfully. Their actual completion timestamps and job/report identifiers
are in [SUMMARY.json](n46d-queue-evidence/SUMMARY.json). PR #9 is the delivery
location; its GitHub merge state is authoritative. Subsequent documentation-only
changes do not alter the tested production, test or build bytes.

## Approved-plan acceptance

| Requirement | Executed evidence | Result |
| --- | --- | --- |
| QB-QUEUE-001: bounded large pages | Both workers process 2,049 chunks as 2,048 + 1; all persisted; exact escaped-byte and vector-value boundaries | PASS |
| QB-QUEUE-002: stale reply rejection | Rechunk/in-place edit on a second connection during provider execution; zero current-batch writes; explicit retry uses current chunks | PASS |
| QB-QUEUE-003: deleted targets | Delete before drain: zero provider calls; delete during reply: zero result writes; delete between batches: no next request | PASS |
| QB-QUEUE-004: truthful counts | Two one-chunk jobs each report one; partial failure reports actual first-batch writes; retry counts only its attempt | PASS |
| One implementation for both entry points | Automatic and generic workers use execute_embedding_job; same four defect scenarios exercised through each | PASS |
| Ownership and current-batch atomicity | Pause/cancel/expiry/reassignment, second-row SQL failure, overlapping worker, progress+vector transaction checks | PASS |
| No DB write lock across provider I/O | Peer connection changes/deletes chunks at provider boundary without waiting on worker transaction | PASS |
| Simultaneous claim contention | 128 two-thread/two-connection barrier races; exactly one active winner; held-lock timeout and setting restoration | PASS |
| Existing functionality | 47 exact native groups; 65 embedding unit, 26 embedding wire, 11 real search/MCP, 51 HTTP checks and existing process/PowerShell suites | PASS within executed scope |
| Delivery integrity | Same-source Windows queue report, 654 exact archive files, 108 artifact readback checks | PASS |

The dedicated native queue executable reports **40 named scenarios / 776 assertions**.
The 128 repeated claim races are part of those assertions, not 128 new product
features. The executable uses real queues, parser, migrations and SQLite, with
only HTTP replaced by a deterministic in-process provider. Separate native WinHTTP
fixtures retain transport coverage; no actual paid service was contacted.

## Review reasoning and compatibility

Provider request limits remain in force. Page/source/content and chunk-set identity
are checked before each batch and before commit; each write also checks exact chunk
id/page/index/text and that no embedding has replaced it. A zero-row write is stale,
not success. Batch vectors and progress commit together; exceptions roll back the
current batch. Previously committed batches remain available for an explicit retry.

Both workers use atomically claimed job ownership; token, attempt, active state and
unexpired lease fence progress and terminal transitions. Late responses cannot
revive paused/cancelled/reassigned work. SQLite waits are scoped and bounded, and
restore the caller's previous timeout. No transaction or SQL statement is held
across provider I/O. The generic worker still counts processed jobs; the automatic
drain counts committed chunks. Job chunks is current-attempt committed writes,
not a lifetime count or a guarantee rows survive later user deletion.

No schema migration, runtime service, MCP operation or provider permission change.
Model labels/dimensions remain enforced in production search/think; FTS still finds
legacy differently labelled pages without automatically relabelling or re-embedding.
Rollback is a code/test/build revert, not a database downgrade.

## Preserved failed test and corrective iteration

The initial 38-scenario candidate 0cbcc031 passed its local interleaving checks,
but a supplemental true simultaneous initial-claim diagnostic failed with
`step: database is locked`. It did not record the completed iteration count.
This failure was not explained away as a CI flake. The plan was amended to add
scoped SQLite waits and two mandatory scenarios. The final 40-scenario suite and
all six focused local CTests passed; final native CI reran the changed source.

Clang ASan/UBSan instrumented the final linked C++ and bundled SQLite C, and all
40 queue scenarios / 776 assertions passed locally. This is not Windows memory
sanitizer or full-program coverage. Old packages were checked and rejected as
repair evidence because they lack the new report and source SHA.

Large-file changes were transferred through hash-checked temporary assembly on a
dedicated branch. Those workflows and patch payloads are absent from the final
source tree; no runtime/build-time patch application is part of the product.

## Package and residual limits

Inner CI ZIP: 1848103 bytes, SHA-256 `4f43e91853602bd141822ad11650ddab9643a3471f8a86bd2c615ffb61c460ee`.
EXE: 3817984 bytes, PE32+ AMD64, SHA-256 `0fae586ddb6d2d12a539c94d87d5a6532da42682e34e3e8d039af140f8058d7c`.
The exact ZIP/EXE/scripts tested by CI are retained; Windows script differences
from Git blobs are limited to the verified LF-to-CRLF checkout conversion.
This is an **unsigned development package**, not a signed production release.

No open P0/P1 was identified in the repaired scope after these checks. Remaining
P2 boundaries: a deletion after preflight may occur after transmission starts;
already sent bytes cannot be recalled. Distinct jobs for the same page, process
crashes or lease expiry can still duplicate provider charges; exactly-once billing
is not promised. Persistent writer contention still produces a bounded error.
PostgreSQL compatibility uses conservative short table locks but real PG integration
was skipped, not certified by a passing outer group. Windows Server CI is not
signed-in Windows 11 Agent acceptance. Model provenance beyond labels/dimensions,
semantic quality, billed cost, ACL/DLP and full project completion remain separate.
