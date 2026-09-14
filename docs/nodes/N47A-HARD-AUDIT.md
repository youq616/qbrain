# N47A stage acceptance — independent reports received

Verdict: **PASS for the explicit evidence-backed fact storage stage**.
Reviewed and natively tested source: `cccdacb61e63c29f8b9eaba1c38fbeed3e23e54b`.
Tree: `a15a91f7172622e2c8021403d84e63bf36f59147`.
Baseline: `9ea592a041965ce5d4ca0d8720908d697b956157`.
This is the coordinator's acceptance record based on the actual independent
source-review reports and separate native evidence. It is not a fabricated new
subagent review, not third-party certification, and not completion of all N47.

## Independent reviews, original bytes

The owner supplied [review A](../review/n47a-cccdacb6/review-A.md),
[review B](../review/n47a-cccdacb6/review-B.md) and their
[summary](../review/n47a-cccdacb6/summary.json) as three standalone uploads.
All three have been read in full and archived without edits. Git blob hashes
returned by the repository match the local upload objects byte-for-byte; lengths
and SHA256 are in [RECEIPT.json](../review/n47a-cccdacb6/RECEIPT.json).
There is no need to recreate the previously described ZIP or repeat the review.
No claim is made to have verified that old ZIP's SHA256 or received the separate
invocation-summary.md; parent invocation receipts are already in the two headers
and the supplied summary. Client identities are reported, not signed attestations.

Both general-purpose reviewers, invoked through the documented ZCode Agent tool,
returned PASS for the same source/tree, no P0/P1, and 13 nonblocking P3 observations.
A reviewed evidence integrity and permissions; B reviewed concurrency, test gates
and compatibility. Their source-only scope and limited Python/SQL experiments
remain explicit: neither compiled the C++ or observed remote CI. The coordinator
checked the actual native evidence separately, rather than attributing it to them.
Report-local environment dates and their wording are preserved, not silently fixed.

## Acceptance against the plan

| Requirement | Independent source review | Native evidence |
| --- | --- | --- |
| Preserve old facts/schema; lazy additive module and pre-write backup | A: original report lines 55-56 | Legacy compatibility and atomic DDL/backup scenarios |
| Complete extracted user quote, no invented confidence/truth | A: lines 44-49 | Unit role/tampering/expiry and CLI/MCP strict input cases |
| Last-support privacy cascade, no superseded revival | A: lines 51-52 and isolated SQL experiment | Native support, forget, retraction/supersession cases |
| Source/write gates and revision concurrency | A: lines 53-54; B: lines 45-48 | Source denial, stale revision, deterministic lock tests and fixed process idempotence schedule |
| Startup lock lifetime and cleanup, bounded wait | A: line 57; B: lines 36-40 | Temporary/persistent startup locks, actual DELETE journal, default timeout restoration and reuse |
| Existing behavior and complete result gates | B: lines 52-65 | 49 named native groups plus original CJK/HTTP/queue/Embedding/Hook/PowerShell suites |

Both [34788803379](https://github.com/youq616/qbrain/actions/runs/34788803379)
and [34788803239](https://github.com/youq616/qbrain/actions/runs/34788803239)
completed all required source, portable, Windows and package jobs successfully.
The first also ran same-source Server 2022 HTTP. Preview publication was deliberately
skipped; that is not a failed product test or a claim of publication.

Actual native results: 49 registered groups; fact unit 15 scenarios/380 assertions;
fact CLI/MCP 34 named checks/118 commands (112 expected exit 0, six expected exit 1).
CJK 72 unit/36 process checks; queue 40 scenarios/776 assertions; HTTP wire 81 checks
on each Windows OS job. Original memory/MCP/Hook/context/config and both PowerShell
suites passed. Real PostgreSQL DSN cases remain SKIP, not PG parity acceptance.
Detailed counts/provenance are retained in n47a-evidence/DELIVERY-CHECKPOINT.json.

The original package/source/native reports were already revalidated by the separate
read-only tool in run 34793874790 (81 checks). This receipt repeated 57 upload/source/
package/report/count checks against externally fixed artifact hashes, reconstructing
the exact 702-file tree. These are evidence checks, not new runtime execution.
Product ZIP SHA256: `1944813712c96e4096058b75b3b7fc18f6a521cf72851413e4a26135f714eee1`.
EXE SHA256: `dead42f5b28d4f296b0b77975e9dbe150f5ac848aac8c6795e2addc7ede53854`.
Both remain original CI bytes and unsigned. No verifier from PR #15 is merged into
the independently reviewed product, and its own independent-review status is separate.

## Thirteen P3 observations and release conditions

Issue #16 preserves all observations; PASS does not mean they were fixed. A-02
(event-scoped forgetting) and A-06 (legacy default-source policy) describe existing
boundaries. A-07 is resolved procedurally: the fixed review task was intentionally
added after the code SHA and is now accompanied by the original reports. Other
behavioral/maintenance changes require a new code revision, tests and stage review.

For B-01, current artifact fact-unit contents were explicitly revalidated outside
the publisher; do not silently re-enable the general auto-publisher before its
permanent check is added and reviewed. A one-time delivery of this exact reviewed,
hash-pinned candidate must verify the full unit/process reports, the original
successful run and these review-file hashes. No new unreviewed executable may be
substituted. Public release status is determined by GitHub, not by this document.
B-02's process barrier supports idempotence, not guaranteed critical-section overlap;
deterministic lower-level locking is separate. B-03's provider_calls flag is fixture
configuration, not a measured network-egress counter. These caveats are accepted.

## Final scope

N47A implements explicit fact storage/lifecycle, not semantic fact inference,
automatic conflict resolution, freshness/decay scoring, user modelling or automatic
fact recall injection. Hashes detect inconsistencies within the stated model, not
an attacker able to rewrite the whole DB and all hashes. Backups/WAL are not secure
erasure. Native tests are synthetic; neither live model costs nor new user-host
acceptance is claimed. Windows scheduling is not a hard-real-time guarantee.

The source-review and original native gates are now satisfied. Subsequent changes
in this acceptance commit are documentation only. Main merge and any release must
use expected immutable SHAs and preserve the original source/test/package identity.
No further local-agent work is needed for this stage's review intake.
