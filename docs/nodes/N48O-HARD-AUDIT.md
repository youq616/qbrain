# N48O final outcome review — PostgreSQL session memory and integrated qualification

2026-09-29. Reviewer: ChatGPT coordinator, explicitly authorized by the current owner
for a separate post-implementation engineering self-review. This is not a subagent,
third-party or Claude Code review and not a guarantee of zero defects.

## Exact accepted scope and provenance

Qualified candidate: `504f2825fe371d3a1b4a867c11f1b66b16a3bc8a`, tree
`33db28742011eb5c8b435dca73a98c6946a30d9e`. Base of this integration:
`a073e24bb0122dfe26d231f045fdb70408169dc9`, tree `1d747e69a8652d5c229d817e282707bdc4a62892`.
Main before PR57: `d038aa1f0ba5df064306ada87d44bf3bc5a43fbf`.

The bounded product module is PostgreSQL support for existing session capture,
extract, read/status, drain and forget. SQLite remains default. This is not the
chat-only proposal for automatic confidence/supersession or real-client consumption,
and does not finish fact_store/context/Hook or all PostgreSQL parity.

The initial runtime and its cd4ca9ae same-connection temporary-table repair were
already in PR57. The a073 integration added an independent semantic reader after
its predecessor missed rehashed quotations, argument changes and error codes.
Those changes are inherited work, not newly authored runtime fixes in this turn.
The previous local-only complete-source-tree supplement is now actually integrated
and remotely qualified. The six-path integration preserves all runtime files,
original semantic readers and tests; static byte/AST checks are recorded separately.

## Findings and disposition

| Finding | Disposition and evidence |
| --- | --- |
| Historical pg_temp relation shadowing | cd4 checks seven effective relation OIDs against public before source/policy access and short transactions, including after callbacks. Fresh native scope112 exercises refusal and whole public before/after states. The unchanged ed79 parent characterization demonstrates its old acceptance, not an accepted runtime. |
| Historical supplemental semantic replay gap | a073's independent reader reconstructs all42 commands, event/item IDs and40 JSON responses, rather than merely accepting saved hashes. That reader remains byte-identical and runs in the final native workflow. |
| Complete-source binding gap in the old pin | Previous local work showed the actual old pin could accept a commit-labeled archive missing runtime code. Current integration binds the independently selected Git tree, full NUL inventory, modes and every blob before and after tests. Oldv1 records do not receivev2 conclusions. Fresh independent Git-plumbing/CLI review accepts12 correct trees and refuses12 code replacements plus12 missing-code archives in each Python mode. |
| Current implementation/outcome review | No additional unresolved blocking finding was identified within the bounded contract and executed checks. No new PostgreSQL runtime defect is falsely claimed; this turn adds integration, independent review and final delivery. |

Content-addressed Git objects and external SHA256 pins detect the exercised source
and evidence mismatches. They are not author signatures, server attestation, compiler
provenance or protection against coordinated replacement of every trusted component.
ZIP checks are bounded and do not extract files, but are not a malicious-file sandbox.

## Review against the approved N48O plan

| Gate | Inspection and executable evidence |
| --- | --- |
| Optional schema and dialect | public UTF8 core, atomic BIGINT module-v1 tables, SQLite-compatible ASCII literal matching; no automatic SQLite migration. Unsupported layouts are rejected. Read/off capture avoid optional memory DDL, not necessarily ordinary core initialization/bookkeeping. |
| Transaction ownership | Database transaction state stays within the storage facade. Active/failed caller transactions are refused, not joined or committed. Short READ COMMITTED sections use fixed sources/pages/config lock ordering and transaction-local2500ms lock timeout. This is conservative serialization, not a throughput guarantee. |
| Provider boundary | Transactions are committed before external callbacks. Returned results recheck effective relations, evidence, lease, tombstone and separate capture/extraction consent. Synthetic callback tests cover revocation and concurrent claims; no paid model is used. |
| Evidence lifecycle | Complete user quotations only, source/fragment identity and conflict refusal, expiry, exact evidence hashes, idempotence, tombstones and preservation of independently edited pages. Independent SQLite process review and real PostgreSQL differential/state tests cover these separately. |
| Permission and isolation | Existing MCP write/source default-deny remains. Same DSN with another brain label is not a separate PG tenant; logical sources are not row-level security. Authenticated DB access and TLS are operator duties. |
| Full source and unchanged regressions | Complete1491-file tree and platform-specific source/script bytes are validated; v2 pretest pins bind source and native executables. Existing real-PG stages, original Windows60/core6 and55-step regression are retained. |
| Delivery and review | Chinese instructions, synthetic example, exact program/source identities, original CI data and separate self-review. Documentation closure cannot alter runtime/tests/workflows and inherit the old verdict. Actual merge belongs to PR57/delivery record. |

The complete PG helper and session implementation, transaction-state facade, plan,
source checker and integrated workflow were inspected. Five inherited gate helper/
lifecycle ASTs and13 important runtime/original-test/build files were checked for
exact preservation against a073. No source-level sanitizer or local full C++ build
is claimed here: unchanged runtime is compiled and executed by native CI.

## Fixed-source native qualification

N48O integrated workflow **36505039842**, attempt1: Linux job109204451200 and Windows
job109204451541 completed successfully. Additional retained N47Z run36505044411
also completed its two jobs; only its job records were reviewed here, not another
pair of downloaded N47Z archives.

| Gate | Actual result |
| --- | --- |
| Native PostgreSQL lifecycle/concurrency | Each OS122 checks; six-connection capture, sole extraction claimant, rollback/timeout, consent/callback and persistence tests. |
| Native relation scope | Each OS112 checks and complete public table states; Linux additionally executes the old parent characterization. |
| Differential CLI | Each OS/mode75 recorded calls:60 product and15psql calls;213 original checks. No omitted PG service is treated as a skip/pass. |
| Integrated SQLite lifecycle | Each OS/mode42 actual calls/110 checks, no native retry in this reviewer.40 semantic JSON outputs reconstructed separately. Not real Agent consumption or PG tenant isolation. |
| New source checker | Each OS/mode25 source-contract tests and10 pin-boundary tests, zero failures/errors/skips. The Windows link-API unit branch uses a controlled mock, not a new native Windows ACL/link test. |
| Original application regression | Each OS55-step driver with exact order/exits/log hashes; Windows original60 registered groups and six core CTests preserved. Nested lifecycle16 and retained18-step records checked. |
| Independent artifact replay | Two external artifact hashes/CRC, exact source1491 files and v2 pins; four full integrated gate recomputations.46 original accounting/lifecycle/MCP/receipt verifier commands run with existing negative controls. |

Qualified program SHA256:
- Linux: `5767f3d7a883d14616a67497861afffdb3a50c8296a14065111bd893afd9a913`.
- Windows: `33084a2f61c7872b6ba08a6e375f0fb0cd1b4ceb736071416a78bbc20c029301`.

Windows source normalization: 1476 files differ only by the exact permitted
text LF/CRLF conversion; remaining source files match raw bytes. Actual Windows
execution occurred in Windows CI, not this Linux environment or the owner's PC.
Server version strings and exact archive identities are in
[n48o-evidence/FINAL-RESULT.json](n48o-evidence/FINAL-RESULT.json).

The original old SQLite44-check harness retains its preexisting bounded contention
retries; observed per-mode counters are recorded, not misreported as retry-free.
No CI retry, permission change or product-timeout extension was requested this turn.
The fixed-source archives expire on2026-10-13; the delivered evidence ZIP preserves
the originals independently of that retention period.

## New local execution and reviewer failures

Local source25 and pin-boundary10 tests pass in normal and optimized Python. Both
old a073 source archives were also checked as1487-file intake baselines, not as
qualification of the new candidate. Independently written source black-box review
executes36 checker processes per mode (12 accepted/24 refused), without importing
the implementation or its fixture builders. Git plumbing constructs expected trees.

The old a073 runtime and then the freshly downloaded qualified Linux executable
were separately run through42-call/110-check SQLite lifecycle reviews in both
modes. Six additional actual qualified-program calls execute the shipped synthetic
manual capture/extract/read/status/forget/replay example. No live provider, real
owner database or local PostgreSQL server execution is inferred from these runs.

An initial combined execution hit the tool time limit after the completed normal
36-call run and part of optimized. The partial optimized directory has no success
report and remains excluded; a new directory completed optimized unchanged. An
unsupported streaming tool request started no test. The first artifact replay
wrapper used relative checker/manifest paths with a different cwd; it failed at
argument/path resolution. Its source/logs are retained; fixing those to absolute
paths did not change tested code or old assertions. Final replay records are separate.

Earlier ODR, Windows PG fixture, pg_temp and a073 reviewer failures are documented
as inherited history. This package does not pretend every earlier raw log was
newly retrieved. The earlier local-only supplements remain historical deliveries,
not current claims that repository writes are unavailable.

## Final disposition and remaining limits

**PASS for the bounded N48O PostgreSQL session-memory module and integrated source.**

No known unresolved blocking defect remains within the inspected contract and
executed evidence. This does not establish universal correctness, high-throughput
scalability, hostile database-owner/filesystem safety, physical secure deletion,
full PG parity, authenticated memory truth or actual logged-in model consumption.
No main/source is replaced outside a normal expected-head PR merge.

The small Windows toolkit is unsigned, contains the exact qualified EXE and the
synthetic example, and does not bundle PostgreSQL/libpq/VC runtime dependencies.
It is not an installer or automatic capture enablement. Existing public releases,
old candidate ZIPs and user data are untouched. Real client use, representative
model quality/whole-pipeline costs, remaining PG modules, signing/stable and Issue40
are still separate acceptance items.
