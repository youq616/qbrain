# N47K outcome review — bounded read-only Hook diagnostic inspection

Verdict: **PASS_SCOPED**. Reviewer: ChatGPT, a separate owner-authorized engineering
self-review after implementation. Not an independent subagent or third party.
No unresolved scoped P0/P1 issue was identified; not a universal bug-free guarantee.
Recorded September 17, 2026. Earlier pending checkpoints remain historical evidence.

## Identity and actual native repair

Baseline main: 03665e99865069a13212d84357b938c8e9cc662d.
Tested product: a23800df3709ac9ef73a51d150b64d2d20d7d21f.
Source tree: b95af421ea5ebb756a127fe8cc519b5b62e17cf6.
All866 original source files were reconstructed to that exact Git tree and were
checked unchanged again after this closeout's supplemental execution.

The initial e9d8f3e1 failed Windows LNK2019 in35178697281, and N42 failed in
35178697254. diagnostics.cpp compiled but both explicit MSVC object lists omitted
diagnostics.obj. Repair a23800df includes it in production and full-test links.
The ten new default closure tests are imported by the existing registry gate;
actual native linking and59-group regression, not static tests alone, now pass.
Old failed runs are retained. No C++ semantics or test assertions were weakened.

## Plan acceptance against code and runtime evidence

| Requirement | Reviewed implementation and falsifiable evidence | Result |
| --- | --- | --- |
| Local-only inspection before ordinary Hook handling | Dedicated hook diagnostics branch; no Brain open, MCP route or Hook stdin processing | PASS |
| Fixed known record selection | Five event names for config.host, exact optional event/session-key; no last-trace or temporary fallback | PASS |
| Strict complete record validation | Unique decoded JSON keys, exact types/ranges, full canonical projection equality, unknown nested fields rejected | PASS |
| No invalid user content disclosure | Non-present slots omit record content; fixed error codes, no raw exception/path/extra field output | PASS |
| Bounded read-only handles |64KiB config,4096-byte records, five slots,32KiB JSON; regular final handles and static ancestor/link checks | PASS within documented filesystem model |
| Historical records remain distinct from current configuration | Disabled config readable; config_enabled independent of recorded state; authenticity/consumption explicitly false | PASS |
| Original compatibility | Diagnostic and original trace/Hook processes; inherited native memory/fact/JSON/lifecycle/HTTP/installer gates retained | PASS |
| Build and delivery identity | Both direct-MSVC targets link; source/EXE/test/script reports and exact original package revalidated | PASS |

Windows uses an OPEN_EXISTING read-only handle with reparse-point and disk-file
checks; POSIX uses no-follow/nonblocking/close-on-exec and fstat regular-file checks.
RAII closes handles on early returns. Static parent checks do not establish a
hostile concurrent-directory or hard-link defense. Independent file observations
are not one multi-file snapshot. OS access-time changes are not excluded.

## Original native evidence now complete

Development35186099196 and N4235186099174 have completed all required jobs on the
exact repaired product. Source, full Windows, Server2022, portable and Linux
ASan/UBSan succeeded. Generic publishers were deliberately skipped, not treated
as release evidence. Both Windows production build and full-test link show their
actual BUILD_OK/TESTS_BUILD_OK and the original registry verifies **59 groups**.

New diagnostic units: **11 scenarios/107 assertions**, on Server2025, Server2022,
portable and sanitizer. Actual diagnostic CLI: **60 checks/68 commands**, on full
Windows, portable and sanitizer, comprising54 expected exit0 and14 expected exit2.
These are isolated documented-host formats, not new signed-in Claude/Codex runs.

Existing N47J trace9/169 and66/80, strict JSON11/95 and54/39, candidate17/647 and43/63,
batch15/259 and40/54, lifecycle17/180 and36/58, promotion18/237 and68/77, Hook13/229
and52/72, recall15/330 and44/71, conflict13/346 and38/75, facts15/380 and34/118 remain.
Both Windows HTTP wire suites have81 checks with fixed cancellation/shutdown
schedules. Queue, CJK, embedding, memory, context and PowerShell5.1/7 consent and
reversible-install gates were retained. Real PostgreSQL DSN cases remain SKIP-PG.
Linux instrumentation is not Windows sanitizer or user-host acceptance.

## This closeout's actual independent execution

Rebuilt unchanged product and diagnostic/trace standalone targets using GCC14.2.0
on Linux. Diagnostic11/107 and60/68, old trace9/169 and66/80, plus69 original Hook
checks passed. Re-ran14 report/registry suites totaling **204 tests**; their31
registry/manifest tests include the ten new link checks, not additional duplicates.
Archive-only wrapper source_commit remains null; source identity is bound by the
externally pinned archive and exact tree, not fabricated Git HEAD metadata.

A new independent dictionary-based CLI probe ran **40 commands/160 assertions**.
It verifies exact complete expected metadata, disabled-config history, invalid
field/count/type combinations, decoded duplicate keys, trailing bytes/raw NUL,
exact4096/65536-byte limits and one-byte-over rejection, no legacy/.tmp fallback,
static symlink and FIFO rejection, exact session filtering and fixed config errors.
Before/after snapshots compare content hashes, mode/size/mtime and topology;
synthetic private markers and paths must not appear in output. This is Linux
fixture testing, not an adversarial concurrent-filesystem or Windows ACL test.
The exact executed source is archived as review_inspection.py with its result hash.

The earlier checkpoint's larger oracle, handle/permission probes and mutation
results are retained as historical checks; they were not repeated or added to this
closeout's counts. A requested streaming container session was unavailable before
any build ran; ordinary container subprocess execution then performed the recorded
build. No tool failure or unexecuted command has been labelled as a passing test.

Six original artifact digests/CRCs, the866-file source tree, all70 product members,
original native report bytes, full mandatory unit/process schedules, current-source
MSVC closure,59 registry names, installer and HTTP evidence passed **318 readback
checks**. verify_candidate.py records this exact offline validation and never runs
a product or publishes. Its uploaded Git blob matches the locally executed bytes.

## Findings and boundaries

The release-blocking native omission is resolved in the tested source. No further
blocking defect was identified in this closeout. INSPECTED or present means schema
inspection succeeded; it does not verify authenticity, host installation, recency,
execution success or model use. Config validation deliberately does not follow
other installer/database paths. Malformed records are independent failures; a bad
slot cannot turn a good slot into success or hide its inspection result.

No new schema, collection/promotion/recall consent, model call, scheduled service
or existing Hook behavior is introduced. Missing/unreadable records are not proof
that an event did not execute. Finite byte bounds are not hard real-time I/O limits.
A local writer can forge valid metadata. No new Codex authentication or live-client
work, signed release, full ACL/DLP, PostgreSQL parity or whole-project completion.

## Exact-byte delivery decision

Original inner ZIP: **2091494 bytes**, SHA256
6f35d1cb1eccb4cdab727963ae45ba805dbc9edfa0c5867472aa62b992b35bb3.
EXE: **4064256 bytes**, SHA256
768eed8abca6168cfbf5ff19bf05a2c0caad81fe579870641e291d6e0c5217ea.
Diagnostic probe binaries were not separately downloaded: identities come from
externally pinned reports and original CI package checks against actual files.
The original tested ZIP and EXE were not rebuilt/repacked by this closeout.

Merge only the reviewed head under normal repository rules, then promote these
unchanged bytes as a new versioned non-latest unsigned preview. Verify all assets
after upload and before publication. Keep generic unreviewed publication disabled.
Actual merge and release are recorded separately; no local-agent task is required.
