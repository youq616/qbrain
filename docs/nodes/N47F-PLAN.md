# N47F — explicit archival and read-only lifecycle inspection

Baseline main: 81a61e02dfb8fde6bb99e8ad38e09fc3e4145e4f.
Status: draft until N47F-PLAN-AUDIT.md approves implementation. Windows Qbrain only.

Earlier conversational N47F descriptions were not implemented. They also mixed
fact status with recall policy and proposed semantic consolidation without an
inference contract. This stage implements a falsifiable first lifecycle slice,
not those unimplemented claims. N47E already combines exact equal local quotes.
Different wordings/languages are NOT automatically merged, and chronological
order does not itself establish supersession.

## Deliverable

Add fact archive / fact restore (explicit writes requiring expected_revision),
and fact lifecycle / memory_read(view=lifecycle) for read-only age inspection.
Use a separate lazy memory_fact_lifecycle_module and memory_fact_archive table,
not new active/stale/archived values in memory_facts.status. First successful
archive backs up an on-disk database before additive schema preparation. Archive
and restore keep object/evidence/status unchanged and advance the fact revision.
A stale revision, unavailable evidence or non-active fact rejects the operation.
No restore revives retracted/superseded/forgotten/expired assertions. Initial
restore of an unarchived fact is a read-only idempotent no-op, without migration.
Existing archives are idempotent only at the current expected revision.

Archive suppresses that fact as a recall anchor (CLI recall and opted-in Hook).
A still-valid archived direct contradiction MUST remain counter-evidence for an
unarchived anchor. Existing explicit fact read/conflicts inspection still sees
archived evidence. This is a recall-organization policy, NOT privacy deletion,
authorization or hiding inconvenient contradictions. Hook's existing filtering
of fact-owned ordinary memory remains, so that channel cannot bypass archival
when fact recall is enabled. Old ordinary-memory behavior with fact recall OFF
is unchanged. No installer defaults or host permissions change.

Lifecycle inspection returns only currently evidence-supported facts, alongside
archival policy and an advisory age assessment. Age is computed from the newest
valid support creation time and an explicit stale_after_days threshold (1..36500,
default180), not recall frequency, source trust, model truth or confidence. It
never changes status, counts a read as use, archives anything or initializes a
module. Invalid/future timestamps are disclosed rather than treated as proof of
freshness. Existing input/source/work/output bounds remain; complete facts only.

A foreign-key cascade removes archive metadata when the fact is physically
removed after final support loss. No copied quote in the archive table; no audit
log of deleted user text. Reads share a coherent SQLite snapshot, including
optional module detection so concurrent first initialization cannot produce a
partly observed policy. Caller-owned transactions are preserved; explicit writes
reject nested transactions. Backup/WAL/old client contexts remain outside secure
erasure claims. Older binaries ignore new archive policy: downgrade requires an
explicit acknowledged rollback, not a claim archival remains effective there.

## Acceptance

Verify fresh no-schema reads and restore no-op, disk backup before initialization,
atomic DDL/transition failure, state/revision checks, retirement/expiry/tampering,
metadata cascade on forget, two-source isolation, FK required, unknown/malformed
module rejection, no raw quote copying, exact read-only accounting, stale boundary
and clock anomalies, old matching query ordering, archived anchors versus mandatory
counter-evidence, opted-in Hook ordinary-memory exclusion, repeated promotion not
unarchiving the same fact, actual two-connection archive/restore and read races,
strict CLI/MCP fields/types and unchanged six-tool/write-deny behavior.

Add one exact native group (54 total), standalone lifecycle unit, actual EXE
CLI/MCP process suite, strict source/EXE/script-bound evidence gates and preserve
all previous Windows/portable/Server2022/PowerShell tests. Do separate outcome
engineering review and fault-injection tests. No native PASS from Linux tests.
No unreviewed auto-publication; any completed delivery promotes only tested bytes.

Deferred: automatic usage counters, confirmation interpretation, semantic merge,
automatic aging/archival, inferred temporal changes, million-event performance
claims, PostgreSQL parity, full model quality/cost and signed distribution.
References: https://www.sqlite.org/isolation.html ,
https://www.sqlite.org/foreignkeys.html , https://www.sqlite.org/backup.html .
