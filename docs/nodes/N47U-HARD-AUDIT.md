# N47U outcome review — read-only receipt audit pages

2026-09-19 (Asia/Seoul). **PASS for the approved source feature. No known unresolved
blocking finding remains in that scope.** This is not an absolute defect-free,
stable-v1, real-client/model or PostgreSQL acceptance statement.
Reviewer: coordinating ChatGPT, separately reviewing implementation and evidence
under the owner's current explicit instruction; not a separate agent or third party.

## Fixed object and continuation

Base main: 4ab3fffc6bb9e6359676a7099d9a9323f02de3d9.
Pre-implementation plan/review: 97c4662fa95dca09ab25aee4ac755db136e7dde7.
Accepted source: b7f93bdce18cfc28e48d4cc7d1ef06a32d901831.
Accepted tree: b7b00cff4bc5dd004ab25889aa5fd366568ceb1e.
Fixed push/attempt1 run: 35445385260.

This continuation found PR38 already open at the above candidate. It read the
approved plan, actual code/diff and completed CI, then downloaded original artifacts,
re-executed the portable binary and authored additional boundary probes. It did
not reconstruct an unseen implementation from an earlier summary or start a duplicate
feature. Product bytes remain the exact candidate; final additions are docs/review
material. The historical approved plan is retained in n47u-evidence/APPROVED-PLAN.md.

## Acceptance against the approved plan

| Criterion | Reviewed implementation and actual result |
| --- | --- |
| Locate receipts without changing them | fact usage-list / memory_read view=usage_receipts returns exact five-field receipt metadata, ordered by ID. Source/eligibility validation is retained; no write route is called. All-table/schema/backup snapshots remain unchanged in the existing-brain tests. |
| Filter states correctly | Current, historical, withdrawn and all sets match independently recorded IDs. Archive is labelled without restoring recall. Current/historical classification is relative to the live fact revision. |
| Complete bounded pages | Limit1–50, result JSON budget512–32768 including CLI newline. Original exact-byte and one-byte-short checks pass. Additional64 filter/limit/budget combinations either return a complete advancing union or reject insufficient budget. No split rows or empty non-advancing pages accepted. |
| Consistent continuation | Snapshot binds source/fact/revision/archive/module state/filter and all validated receipts. Both cursor fields required; cursor must belong to the filtered set. New lower IDs, withdrawal and version changes reject; duplicate no-op reports and changed page size preserve meaning. |
| Validate before filtering | At most4097 rows check the4096 capacity. Off-page/off-filter malformed IDs, BLOB types, future revisions and bad times reject instead of producing partial counts. |
| Permissions and eligibility | New read view stays in the existing resolver; listing an ID grants no write permission. Wrong-source and default-denied revoke are tested. Supplemental natural-expiry and retired-fact probes deny even a previously valid cursor without changing rows. |
| Regression and source identity | Two actual new binaries pass71 page checks/111 commands and75 unchanged use checks/118 commands, plus retained process suites. Fresh Windows60 groups and Linux4 focused groups pass. Both original artifacts, source trees, test/binary identity and raw page streams rechecked. |

The source adds fact_usage_read.hpp and modifies only the existing route/schema
advertisement and fact CLI/help. N47T fact_usage.hpp, original FactStore, Hook,
retrieval, installer, old tests/build scripts, ledger and frozen inventory are
byte-identical. No persistent schema or new MCP tool is added.

## Actual CI, executable and raw-file evidence

Both jobs and every required step completed/success:
Windows105903305987; portable105903306130. The workflow freshly compiled each
changed engine and used that executable for its new and retained process gates.

| Original artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| portable10584808662 |14676929|af1dfc13a948da658e7814fdd3489264fc413eba60a4b96c2993f26e906eaa10|
| windows10584674025 |14281684|e7480fa4366e65e2065c7d6b294fedb823dba8084d99c09763e0bdf4fe3fdc0a|

Archives have362/361 members respectively and valid CRCs. The nested1140-file
canonical archive reconstructs the accepted Git tree. Windows membership/modes
match;1126 files differ solely by exact LF-to-CRLF conversion. Of352 inherited
code/test/build files compared with the preceding N47T source, only commands.cpp
and memory_ops.cpp differ; the audit header and new test/checker/workflow are additions.

Windows executable SHA256:7f8f48c3e34510ad050993904927288a1f2625710917fd986bc8a06df3b72f7e.
Portable executable SHA256:7399af97dde5b97cc87667dc7e0e3fbdbf79b8b435fbfb62f01f2cb4cfd4e57e.
Both bytes were downloaded. Only the portable executable was additionally executed
in this Linux review environment; no local Windows or newly compiled local EXE is claimed.

Each platform's71-case report binds111 calls and333 saved stdin/stdout/stderr
streams, including33 successful page responses. The source-owned checker reread
all of them, exact page fields/IDs/order, budgets, cursor results and error shapes.
Fourteen malformed-report cases reject under normal and optimized Python in CI;
local repeat also passed. Fixed-source outputs retain synthetic data only.

Retained per-platform checks: original use75; fact34; context65; multiterm112;
named arguments60; search arguments226; Hook facts52; lifecycle batch40; memory44;
MCP17. Original fact/multiterm/Hook/batch report validators were rerun with matching
source, script and executable hashes. Other original reports/logs and actual CI
steps were checked without claiming new independent raw bodies where none were saved.
Windows native log has BUILD_OK and all60 registered groups, with the exact60
validator receipt. Linux CTest has4/4. PG is explicitly SKIP-PG, not an accepted DSN test.

## Separate black-box probes and preserved failure

The new docs-scoped review_boundaries.py was executed twice against the exact
portable CI binary, normally and with Python-O:14 checks,215 real CLI calls each.
These include64 matrix combinations, off-filter withdrawal invalidation, unrelated
fact-write stability after module initialization, support-only revision changes,
retired eligibility, positive pre-expiry reads followed by actual clock expiry,
read nonmutation, and forgetting expired last support. All successful CLI bodies
are checked against selected byte budgets; full synthetic requests/responses are
retained in the local reports. Setup uses public writes; SQL is read-only for state
snapshots and locating generated evidence identities. No test-only production flag.

The first supplemental run failed while preparing its expiry fixture: it assumed
the public memory view exposes every duplicate quotation. That view intentionally
deduplicates quotes, so the newly captured event was not always visible. The fixture
now reads the generated event's item identity by a read-only SQL lookup and confirms
its quote remains present in the public view; it does not seed SQL data or change any
production assertion. Initial failure and final normal/optimized report hashes are
retained in SUMMARY.json. No production defect was inferred from this fixture error.
The accepted original71/111 test and prior75/118 test were also rerun locally with
the downloaded portable binary and passed; their source files were not changed.

The independent matrix is broader coverage, not proof of all concurrent schedules.
The expiry probe validates real passage of time and refuses a setup lacking its
pre-expiry margin; it is not a wall-clock-independent fixture. The additional
probes ran on Linux, not a separately authenticated user's Windows11 machine.

## Boundaries and outcome

One read request keeps an active SQLite statement to retain its read snapshot;
a token is only a fingerprint checked anew on a later request, not a lock, a
signature or a write capability. SQLite transaction behavior was checked against
https://www.sqlite.org/lang_transaction.html and https://www.sqlite.org/isolation.html .
No changes from a separate connection are expected inside that same read transaction;
there is no promise of a transaction or historical archive spanning different requests.

Every page intentionally inspects the whole bounded receipt set. There is no
large-scale latency guarantee. Metadata on invalid/retired/expired facts is not
made public just to find a revoke ID; an already-known receipt can still be revoked
under N47T rules. Module initialization is part of the fingerprint, so the first
use-module creation may invalidate an earlier empty-set token. A restored identical
database can reproduce its old fingerprint; malicious rollback is not detected.

Read-only claims concern this feature on an existing brain. Generic inherited
CLI opening/initialization behavior is unchanged. The byte budget describes the
tool-result JSON plus CLI newline, not the MCP protocol envelope's extra escaping.
New PowerShell documentation was checked against interfaces, not claimed as a new
native installer execution. No receipt read is counted as usage, fact confirmation,
profile, ranking, decay or observed host/model consumption.

PR38 can merge after the final docs-only diff and head/tree checks. A merge-triggered
new CI must not be announced successful in advance. No Release/tag is created or
replaced; N47R public binaries do not contain N47T/N47U commands. Original artifacts
retain their stated2026-10-03 expiry; Git stores precise hashes/derived receipts and
reproducible review code, not the complete original binary archives. Remaining real
client/model/fee/PG/signing and full-project gates are not closed by this source feature.
