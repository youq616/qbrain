# N48R outcome review — PostgreSQL Hook admission and combined snapshot

2026-09-30 (Asia/Seoul). Reviewer: ChatGPT coordinator, carrying out a separate
post-implementation engineering self-review under the owner's current authorization.
Not a third-party, Claude Code or independent-subagent certification.

**Verdict: PASS for the bounded N48R module and the executed acceptance scope.**
No known unresolved blocking implementation defect was found. This is not a claim
that every possible defect has been excluded or that the whole project is finished.

## Exact qualification and attribution

Main before integration: b4793e2a1694fbd2668aaf5880f51b4c5dc34bff (N48Q).
The runtime already existed at intake in PR60:45a238534e67c173b6baa4f2ed257f6117b72044,
tree00405f2f2c78776f304656ed730787839ee04ee7. Its original full native qualification
is run36583542753. This continuation did not newly author that runtime implementation.

The new independently written reviewer, supplemental native workflow and approved
closeout plan were integrated with main in6481b330. Fixed reviewer commit
**a4acb118197ad1205ddce086f83f6461ccedbb06**, tree
**faa070dca23c1e43b4ce6a28d39a00a17d35bdf9**, completed supplemental run
**36652734242**: Linux109690337024 and Windows109690337203 both success, attempt1.
Runtime, original tests, CMake and original full Hook driver/workflow are unchanged
from45a23853; both runner comparisons and independent archive blob checks establish
this, not merely PR descriptions. Closing documentation is not another binary build.
Actual merge identity belongs to PR60 and the separate delivery record.

## Review against the approved plan

| Contract | Inspected implementation and actual evidence |
| --- | --- |
| Existing-only PG admission | hook_storage.hpp opens only the requested PG backend, checks public/UTF8/origin, effective core table resolution and core version13, then loads configuration. No pg_ensure_schema, source registration or SQLite fallback. Direct tests and new process probes reject empty/unknown/unreachable/non-public PG while a populated local SQLite brain exists; its bytes stay unchanged. |
| Consistent combined recall | Hook creates its own REPEATABLE READ READ ONLY fact scope. The private session reader requires module ownership, an active transaction, correct namespace and server-confirmed read-only/repeatable-read settings. Real two-connection tests observe one pinned snapshot across a concurrent committed forget, then observe the deletion on a new read. |
| Caller ownership preserved | Ordinary memory read/forget and Hook composition reject caller transactions. Active, failed, arbitrary read-only and module writer scopes remain caller-owned. Negative tests verify refusal and retained transaction state; temporary-table conflicts do not leak a module scope. |
| Evidence, withdrawal and permissions | Full facts, supporting IDs and ordinary quotes retain source/role restrictions and untrusted-data flags. Inactive/equal-quote facts suppress the legacy lane. Complete groups fit the byte budget or are omitted. Reads end before independently permitted capture/extraction/promotion. Shared off and per-install capture refusal leave application-row counts unchanged. |
| Effective database dedup | The legacy recall state hashes the effective server/database/role descriptor in PG mode. New actual process probes create identical event/item IDs in two dedicated databases: first A emits, repeated A suppresses, B emits, returning A suppresses, SessionEnd resets A. Descriptor and DSN are not output. This is not a hard tenant boundary. |
| Diagnostics and actual host scope | Original role/secret/project negatives and new bounded metadata checks pass. No raw user prompt or test connection password appears in checked trace projection. Synthetic adapter events execute actual Hook processes; no signed-in Claude/Codex or model-consumption claim is made. |

Reviewed the complete new admission/private-reader headers, changed Hook and
session-memory implementation, fact transaction ownership, evidence suppression,
original native/process tests, original/full and supplemental CI, and the new
reviewer's input/exit/output handling. The reviewer uses no product or original
fixture imports. Checks remain executable with Python -O.

## Actual test results and original evidence

Original run36583542753 (45a23853) completed Windows/Linux real PG qualification.
Each OS: native Hook80 checks (20SQLite/60PG and setup), original fact228/context198/
session122/table-scope112, eight CTest groups. Each Python mode: original Hook127
recorded calls/262 checks, of which95 product and32psql. Its25-step driver includes
retained55-step application regression. The Windows registry independently verifies
60 required groups. The legacy optional N38 PG integration group is explicitly
skipped in that registry; it is not counted as a full PG test. Real N48O/P/Q/R
server-specific tests run separately and passed.

Original archives were downloaded, external size/SHA256 checked, CRC checked and
all1528 source entries verified against Git blob IDs. Linux1528 exact; Windows16
exact and1512 exact LF/CRLF conversions only. The complete Git tree00405f2f was
independently reconstructed. The original raw reader checks all4 reports and220
Hook outputs, reconstructing complete user quotes, IDs, support fields, envelopes,
source/role flags and retired results; each report rejects6 semantic mutations.
Every original25-step and retained55-step log hash/exit is checked. Four complete
old integrated-gate replays pass (two OS archives, two Python modes); these are
output replays, not another execution of every product command.

Supplemental run36652734242 (a4acb118) freshly builds complete programs on both OS.
Actual servers: PG16.15 on Ubuntu24.04 and PG14.24 on WindowsServer2022. Each OS runs
native Hook80 plus the two original Hook-related CTest groups. Each OS/Python mode
runs independent SQLite26calls/70checks and PG58calls/124checks (38product/20psql).
The two new archives have1540 source files each; their complete treefaa070dc and
runtime/original-test equality were independently reconstructed. Windows16 files
are exact and1524 differ only by exact LF/CRLF conversion. All1008 raw streams in
the8 new reports match recorded hashes and successful exits; all152 Hook outputs
are parsed, admission/retirement and exact two-lane outputs checked, and dedup
sequences independently rebuilt. This is not a claim of additional mutation tests
on the new report format. Pre/post binary and reviewer identities match.

Fresh local Clang build: eight CTest groups, native Hook20 and original Hook13
scenarios/229checks passed. Original SQLite Hook47calls/111checks per mode, legacy
Hook69 and memory-cycle44checks per mode passed. The corrected independent reviewer
passes26calls/70checks in normal and optimized modes. ASan/UBSan (PG disabled) passes
new20 and original229checks; both diagnostic stderr files are empty. There is no
local PostgreSQL server and no owner's Windows11 execution.

## Failures and corrections are retained

First supplemental run36652056812 passed Linux; Windows built and passed both
CTest groups and native80 but failed reviewer TemporaryDirectory cleanup with
WinError32. Its26calls/70checks were all true, but the overall result remains FAIL:
SQLite's transaction context did not close the reviewer's connection. a4acb118
adds contextlib.closing around that context; no cleanup error is ignored. Runtime,
assertions, timeouts and workflow are unchanged. New complete matrix36652734242
passed. Failed artifact11070379720 was independently downloaded/SHA256/CRC checked
and its PARTIAL report retained; no old failure is relabeled as success.

Offline reviewer development also retained an incorrect nested exit-field
assumption and Windows log separator error. Old gate replay initially passed a
CRLF-terminated pin, then used a Linux-newline checker against Windows source
identities. Final replays use stripped external pins and the exact archived
Windows checker bytes. These are review-driver errors, not erased product results.
Earlier MSVC missing standard includes were fixed by the inherited45a23853 commit;
its earlier failed run36582687418 is historical, not a newly authored fix or a
newly downloaded original failed artifact in this continuation.

## Scope, deployment and disposition

No owner data, live provider account, paid model traffic, signing credential,
public Release or old fixed ZIP was used or replaced. Windows programs are unsigned
and require compatible VC/libpq dependencies. The delivered executable is the new
supplement build, whose SHA is recorded separately from the older full-run binary;
identical source does not mean all separately built Windows binaries have equal SHA.

Existing-only admission is not exhaustive schema attestation against a malicious
SQL owner. Same DSN/another brain label is not tenant isolation; source is not RLS.
The Hook statement budget does not bound every DNS/network/OS operation. Existing
host supervision, Issue40, real client lifecycle/consumption, representative model
quality/full-pipeline cost, remaining requirements and signed/stable release retain
their own acceptance gates. No new MCP operation or public registry count is added.

Final disposition: no unresolved P0/P1 finding in this bounded module. Deployment
and whole-project gates above are not silently converted to passed tests. After
qualification only documentation, historical snapshots and already executed review
sources/results are added; compare exact closing tree before normal expected-head
merge. [RESULT.json](n48r-evidence/RESULT.json) records detailed identities;
[Chinese guide](../integration/POSTGRES-HOOKS.zh-CN.md) describes safe use.
