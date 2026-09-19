# N47T final outcome — explicit fact-use receipts

2026-09-19 (Asia/Seoul). **PASS for the approved production-source scope; no known
unresolved blocking finding remains within that scope.** This is not a guarantee
of absence of all defects, a stable-v1 acceptance, or real client/model validation.
Reviewer: coordinating ChatGPT, in a separate engineering outcome review under
the owner's explicit instruction. No separate agent or third-party reviewer ran.

## Review object and scope

Base main9694ffed4ab2c8f73377c469c9031087c830b94d. Plan/plan review was committed
in45a0dd724270c9bef9910231fd6d4325b151d2e1 before implementation.
Accepted source **6e6ca6e8c136fbfd81ee8671c42cfc172a350db7**; tree
**ff094b291f9c5177dc250be6c09ab6acf4b64409**. Actual fixed push/attempt1 CI:
https://github.com/youq616/qbrain/actions/runs/35440959490 .

Production adds include/qbrain/memory/fact_usage.hpp and touches only existing
memory_ops.cpp routing/schema descriptions and fact CLI/help in commands.cpp.
The original fact_store implementation/header, Hook, retrieval, migration version,
installer, native tests/build lists, canonical ops ledger and frozen inventory
are unchanged. New routes reuse memory_read/write; no MCP tool name is added.
An initial local in-file implementation was refactored into this route-local
module before the accepted commit; the original FactStore is restored exactly.

## Acceptance against the original approved plan

| Criterion | Code review and executed evidence | Result |
| --- | --- | --- |
| Explicit bounded receipt | Strict JSON fields, lowercase64hex IDs, integer current revision. Caller-controlled counts/times/origin fields reject. Responses explicitly label caller_reported, no truth or host-consumption proof. | PASS |
| Active supported revision only | Reuses public FactStore complete-evidence reads, checks active status, exact revision and archive state. Incomplete evidence budget fails closed. Separate real-expiry probe rejects use and reads after support expiry. | PASS |
| Idempotence and withdrawal | Unique source/usage key; IMMEDIATE transaction revalidates fact. Four concurrent cold duplicates produce one record; eight distinct concurrent records all persist. Repeated withdrawal retains its timestamp; withdrawn IDs cannot resurrect. | PASS |
| Version isolation | Attach/forget revision changes move previous receipts to historical counts rather than current counts. Separate probe rejects reusing an ID with a new revision even when that new revision is valid. | PASS |
| Optional schema and backup | Reads, absent-receipt withdrawal and preflight errors do not initialize the module. First valid write backs up before module creation; snapshot probe compares exact prior fact rows and verifies absence of new module in backup. | PASS |
| Cleanup and retention | Last-support forgetting deletes facts and cascades active/withdrawn receipts. Independent remaining support retains history with revised current identity. Expired receipt can be withdrawn and later explicitly forgotten. | PASS |
| Capacity and failed writes |4096stored receipts including tombstones; at-cap duplicate succeeds, new ID rejects without eviction. Named SQL trigger abort rolls back insert; same ID can subsequently retry. This is a simulated database-write error, not a physical disk-fault test. | PASS |
| Source/write authorization | Existing resolver/registry retained. Real MCP default-deny, explicit authorized write/read, wrong-source denial and source-independent IDs exercised. Network capability check remains centrally before dispatch; no new bypass. | PASS |
| Reads do not report use | Actual usage/read/recall/lifecycle snapshots preserve application rows; actual Hook read does not add a receipt. Existing fact content/revision stays unchanged by reporting. | PASS |
| Native/regression and extra review | Both actual-platform75/118 gates and all retained process suites pass. Fresh MSVC production/full60 groups pass; fresh Linux4focused groups pass. Separate12-case probe and14malformed report probes pass/reject as specified. | PASS |

The new optional SQLite tables are real schema additions, though no global schema
version changes. There is no claim that the feature is schema-free. Existing
FactStore backend validation explicitly refuses PG; the full native PG group
contains SKIP-PG and is not counted as genuine PG integration acceptance.

## Actual native runs and original artifacts

Both jobs and every required step completed/success:
Windows105891540938 and portable105891541030 in run35440959490.
The fresh production binary built in each job is the one its new and retained
process tests use. Windows uses original scripts/build-tests-cl.ps1; no existing
assertion, test group, object list or workflow was weakened.

| Test per platform | Actual result |
| --- | --- |
| N47T new process suite |75/75 checks;118 commands |
| Original fact process |34 checks;118 commands |
| Original context process |65 checks |
| Original multiterm process |112 checks;126 commands |
| Original memory/context named arguments |60 checks;113 commands |
| Original search arguments |226 checks;302 commands |
| Original Hook fact process |52 checks;72 commands |
| Original lifecycle batch process |40 checks;54 commands |
| Original memory / MCP boundaries |44 /17 checks |

Windows original full suite:60 registered groups, with BUILD_OK and the native
validator's60 receipt. Portable original focused CTest:4/4 memory/context/fact/
multiterm groups. The new75 checks are test scenarios, not75 separate features.

Original artifacts downloaded and checked against live connector metadata:
- Portable10584171527:14547730bytes; SHA256
  4bd5f4f12dab1ed5499c83f3f787d7e36dcc029ca31a600930b1b4d2299b6506;25members.
- Windows10583269479:14153333bytes; SHA256
  050f3625594bf9c52c3d677c715e7d43fe773f9d7e15920d09e977330602fc2c;24members.

Both ZIP CRCs, source markers and report identities were inspected. Canonical
Linux source reconstructs1127files and the exact accepted Git tree. Windows has
identical membership/modes;1113files differ solely by exact LF-to-CRLF conversion.
The259 inherited runtime/test/script files compared against the prior accepted
runtime differ only in commands.cpp and memory_ops.cpp; fact_usage.hpp is new.
The accepted new module/route/CLI/test blobs also equal the locally tested files.

The source-owned usage report checker was rerun with each downloaded executable
and its exact native test-script bytes. Four original fact/multiterm/Hook/batch
report validators were independently rerun, including fixed-source, script/EXE,
checks, command-history and exit assertions. Other retained reports/logs and all
required CI steps were checked. Tests execute semantic assertions inside temporary
brains; the new harness retains hashes and exits, not every individual stdout
body. This audit does not claim to observe already-deleted test directories or
independently replay unavailable stdout bodies.

## Separate self-review executions and retained limitations

Final local GCC product built from the exact changed files passed75/118, the nine
retained process suites and4focused CTest groups. The local root is extracted
source, not a Git clone; no fabricated local commit identity is used.

A separately authored probe checks missing withdrawal without schema creation,
exact backup fact rows, cross-revision ID collision, real clock expiry, expired
withdrawal and expired-fact forget cleanup. It passed12checks/24commands on both
the final locally compiled Linux binary and the actual downloaded portable CI
binary. These additional probes ran on Linux, not on the owner's Windows system.
The test-only script is n47t-evidence/extra_review.py.14 malformed report mutations
(wrong count/schema/hash/type/case/command/exit/scope or binary/script identity)
were rejected by the unchanged report checker. This validates content constraints,
not an arbitrary caller's authenticity.

| Binary | SHA256 |
| --- | --- |
| Native Windows CI product |7b5d8eda7af757724b6441d60b72020d8a1c8c16c758906ff037f1ddc9a0d93d |
| Portable CI product, separately executed |dbcbbbba1124feea8597ef8f837ac2da0d375e182192da8b2500bf481a1eb482 |
| Local GCC product |00a580de3ba6a136f027ab7e67958cfa1ff97b7481ce0025dffb042b8fd67ef7 |

Windows EXE bytes were downloaded and hash-checked, not executed in the Linux
review environment. They are not the old released c26 EXE. No new application
package is released in this node.

Initial local harness incorrectly used unsupported memory read --event and
failed before feature testing; corrected to public read plus event filtering.
Its failed report is retained in conversation evidence. The first supplemental
probe's short five-second expiring fixture found no item during seed preparation;
it did not reach the expiry assertion. With a ten-second preparation window,
the test waited for actual expiry and passed on both final Linux binaries. The
initial failure is not erased or reclassified as a successful test. A timed-out
initial combined configure/build invocation was superseded by individually
recorded successful builds. No product gate was bypassed by these corrections.

## Remaining bounds and merge decision

No known unresolved blocking issue was found in this scoped review. First schema
preparation and actual use insertion are separate transactions; a concurrent fact
change can leave an empty initialized module/backup, but not a false receipt.
Cold concurrent preparation can produce more than one complete backup. Capacities
are per fact, including revoked tombstones, not a global disk quota. Summaries
require full public fact eligibility and may refuse large/complex evidence. A
retracted/expired fact is not made readable merely because it has old receipts;
known receipts can still be revoked. Earlier valid-state duplicates do not bypass
current revision/archive validation after a later fact change.

Caller reports can be false. They do not become automatic truth, observed model
use, consent, ranking, semantic confirmation, profiles or decay. No guarantee
against an administrator replacing database schemas/files is provided. Expiry is
filtering, not immediate erasure; backups/WAL may retain data. PG, actual paid
models, authenticated client consumption and code signing remain unverified.

The limited source feature is acceptable for merge after checking the closing
non-product diff and current heads. Only docs, history and the already-executed
docs-scoped probe are added at closure; the tested product/test/workflow remain
6e6ca6e8. Record actual merged tree in PR37. Do not predeclare merge-triggered CI
or a new public Release. This advances broad-roadmap use recording, not the
missing external v1 gates; v1 remains conditionally3–4 further substantive rounds
and the broader route15–25 inclusive. Neither interval is a fixed commitment.
