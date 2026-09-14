# N47C outcome review — query-directed recall with counter-evidence

Verdict: **PASS for the scoped N47C implementation**. Reviewer: ChatGPT, separate
engineering self-review under the owner's explicit instruction. Not an independent
subagent or third-party audit, and not certification of all N47 or the project.

## Reviewed identity

Baseline main: `309d71ab79e8bfb55f8b8161ec0126e80514e965`.
Actual product: `1311bdd51b779e8da6b6420b62ea3f653edfa27f`.
Actual source tree: `360cfd7a303ac2f3084cef66917378a22dae6272`.
The original source archive contains 731 files and reconstructs that exact tree.
Administrative transfer payloads/workflows are not in the product tree. This
outcome pass does not change production code, existing tests or packaged bytes.

## Plan acceptance

| Requirement | Code review and falsifiable evidence | Result |
| --- | --- | --- |
| Usable query-directed fact recall | FactStore::recall, fact recall --query, existing memory_read(view=recall) | PASS |
| Matching before the cap | Bound literal predicate before LIMIT; old match behind over 100 unrelated facts tested | PASS |
| Complete counter-evidence | Every valid active direct contradiction neighbor included even without query text, with complete original quotes/revisions/provenance | PASS |
| Explicit direct-neighbor scope | No transitive expansion; matching neighbor remains its own anchor with its other edges; independent graph oracle | PASS |
| Coherent snapshot and call-local work | Outer SELECT remains live during endpoint loads; second real WAL connection commits forget during deterministic interleaving; next call observes deletion | PASS |
| Whole-group byte/work limits | Exact fit/one-byte-short, result/candidate/relation/evidence-work limits; incomplete group never emitted | PASS |
| Permission and compatibility | Source denial, six unchanged MCP names, strict irrelevant-field/type rejection, original facts/conflicts/memories tests | PASS |
| Read-only behavior | Write-denying authorizer, unchanged schema/revisions/jobs, no new provider code or consent | PASS within fixture scope |
| Defensive input handling | UTF-8/NUL/length validation, bound SQL, literal wildcard text and oversized damaged counterquote precheck | PASS |
| Native regression and packaging | Exact 51 registered groups and source-bound unit/process/package evidence | PASS |

Only existing explicit contradictory assertions are returned. Matching, active
status or the existence of an edge proves neither truth nor falsity. The query
is literal substring matching, not embeddings, segmentation or semantic inference.
No automatic Hook insertion, new schema, tool name or write authorization.

## Supplemental outcome pass

Rebuilt the unchanged implementation with Clang 17 and AddressSanitizer plus
UndefinedBehaviorSanitizer for bundled SQLite C and application C++. Halt-on-error
was enabled. All 15 scenarios/330 assertions and the real 44-check/71-command
CLI/MCP schedule passed without a sanitizer diagnostic. This is additional Linux
instrumentation, not a Windows sanitizer or new user-host acceptance.

A separate deterministic Python graph oracle used the real CLI and independent
expected adjacency sets, not FactStore's query as its oracle. It created two
sources with 24 vertices each and respectively 18/17 explicit edges. Initial,
retracted and forgotten graph states were checked for exact direct-neighbor sets,
complete provenance, ordering and budgets. Eighteen budget/limit combinations per
source/state were included: 180 checks and 294 real commands passed on both GCC
and sanitized builds. Repeated runs are not additional unique user scenarios.
Local archive-only reports correctly retain source_commit=null; exact source
bytes are separately bound by the reconstructed archive tree.

Two deliberately broken copies were compiled and exercised, without touching the
candidate: omitting direct counterclaims failed `nonmatching counterpart retained`;
bypassing byte-budget rejection failed `cannot return anchor with only some
counterclaims`. Both returned exit 1 as required. This confirms those assertions
catch the corresponding defects, not that every mutation or bug is covered.

Outcome-pass report-gate tests also passed: recall 10, conflict 10, fact 12,
CJK 10, HTTP lifecycle 14 and registry 13 (69 tests). Expected failing fixtures
remain failing; no assertion or ceiling was removed to obtain passing evidence.

## Findings and retained failures

During implementation, review identified that a damaged database could cause an
oversized counterpart object to be loaded before checking its size. The final
candidate adds a source/status/subject/predicate/object-length precheck before
materialization and a regression. This was fixed before 1311bdd5; no post-review
product change is hidden under the original candidate's test evidence.

An initial local call to the old fact-unit wrapper failed because an archive-only
directory lacked Git HEAD metadata. That failure is retained; the unchanged direct
unit binary subsequently ran successfully. The wrapper was not weakened or its
source field fabricated. Source-bound native CI is separately validated.

Nonblocking limits: the first oversized group stops later groups even if they
might fit; empty+truncated does not establish no result. Matching anchors may
repeat counterpart facts intentionally. Direct-neighbor-only results are not
full connected components. Query/work/result bounds do not impose a SQL row-scan
or hard real-time limit. Hashes do not defeat an actor able to rewrite the whole
database and recompute them. Existing default-source policy and N47A P3 follow-ups
are inherited, not silently changed.

No unresolved P0/P1 issue was identified within this scope. This is not a promise
of bug-free software. Snapshot semantics allow an in-progress read to return a
complete pre-forget snapshot; the next call sees the committed change. The test
uses two real connections with deterministic interleaving, not a claim that two
threads overlapped by chance. SQLite references used in the design:
https://www.sqlite.org/isolation.html and https://www.sqlite.org/lang_transaction.html

## Native evidence and delivery

Development run **34854466927** and N42 run **34854466971** completed successfully
on 1311bdd5. The development run includes source, portable, complete Windows
build/regression/package and Server 2022 HTTP plus the new recall unit. Old generic
publication jobs were deliberately skipped and do not establish a Release.

- Windows exact registry: 51 groups; real PostgreSQL DSN cases remain SKIP-PG.
- Recall unit on Server 2025, Server 2022 and portable: 15 scenarios / 330 assertions each.
- Recall CLI/MCP on Windows and portable: 44 checks / 71 commands each, with
  66 expected exit-0 and five expected negative exit-1 results, not all-zero exits.
- Previous facts: 15 scenarios / 380 assertions and 34 process checks / 118 commands.
- Previous conflicts: 13 scenarios / 346 assertions and 38 process checks / 75 commands.
- Each Windows HTTP job: 81 wire checks, fixed four-variant cancellation schedules,
  two current processes with 256 cancellations each and explicit cache shutdown.
- CJK: 72 unit / 36 process checks. Queue: 40 scenarios / 776 assertions.
- Embedding unit/wire/search: 65/26/11; memory/MCP/Hook/context/config: 44/17/69/65/6.
- Each PowerShell 5.1 and 7: installer 69, consent 16, transport 8.

Downloaded five original artifacts, checked their external API digests before
interpretation, reconstructed the exact 731-file Git tree, and completed **162
readback checks** on source identity, inventory, original report bytes, complete
unit scenarios/assertion sums, expected exits, script/EXE hashes, registry and
both HTTP schedules. The readback itself runs no product executable.

The exact tested inner ZIP has **1,942,131 bytes**, SHA256
`bc707db523de36b026ed302f4824afdbfd614bf8efbcc9a93a885f74d68fd3bc`.
EXE: **3,922,944 bytes**, SHA256
`91f31494dec86ae1e298f0cd4aa5cbd95c727aa0fffd71bb87ce6d6d6be9601f`.
Neither delivered ZIP nor EXE was rebuilt/repacked in this outcome pass. They
remain unsigned. Exact artifact IDs/digests and supplemental log hashes are in
`n47c-evidence/SUMMARY.json`.

Diagnostic probe executables were not separately downloaded here; their hashes
come from externally pinned original reports and the original package job's
checks of actual probe files. Do not relabel this as independent probe readback.

The stage can be integrated and this exact tested ZIP promoted to a new versioned
non-latest preview with source identity and asset readback. Do not overwrite an
older Release or enable general unreviewed auto-publication. Rollback is a source
revert, not a database downgrade. Real PG parity, signed-in host integration,
paid-provider quality/cost, semantic extraction/conflict decisions, profiles/decay
and automatic fact Hook recall are not certified here. No user-machine task is
required for this repository implementation and validation.
