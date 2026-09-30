# N48Q outcome review — PostgreSQL facts, lifecycle and explicit receipts

2026-09-30 (Asia/Seoul). Reviewer: ChatGPT coordinator, performing a separate
post-implementation engineering self-review as expressly requested by the owner.
This is not a third-party, Claude Code or independent-subagent certification.

## Disposition and exact source

**PASS for the bounded N48Q source module and its tested supplementary review.**
No known unresolved blocking defect was found in the reviewed code and executed
contract. This does not prove absence of every defect or complete the whole project.

Main before this module: cfa00185dc0575b1dbf7c418082608f7563a3b91.
Runtime qualification candidate: 4f8b470f32df106c9bb596f24252ffb800773b47,
tree927600dc124416fe0701b03d21e28274f3e83b27.
New supplementary candidate: 28d64ae7bb93eaf33b6db48c25314fe721bc4823,
tree511b6a9c5aae6edf2a3a001e4dd1d966badb59cf.
Actual merge identity belongs to PR59, not an earlier frozen execution report.

The PostgreSQL implementation already existed in PR59 at intake. This continuation
adds the closeout plan, independently written .ci/review_pg_facts_closeout.py,
.github/workflows/n48q-outcome.yml, usage documentation and this outcome review.
It does not misattribute the existing runtime implementation as newly authored here.
The new native jobs check git diff against4f8b470f for src/include/tests/CMakeLists.txt
before testing, and check their tracked runtime/test/reviewer files again afterwards.
These executed checks show the runtime and old native tests remained unchanged.

## Acceptance review

| Approved gate | Code and executed evidence |
| --- | --- |
| Source and effective-table binding | Inspected pg_fact_storage.hpp and module call sites. Fifteen relation names are bound to expected public objects, public/UTF8/origin context is checked, and temporary-table shadowing is rejected. Native tests exercise all fifteen names, caller active/failed transactions and cleanup after refusal. |
| Consistent reads and owned writes | Module-owned REPEATABLE READ READ ONLY scopes support internal evidence reads but do not commit a caller's transaction. Ordered source/page/config/dependency locks and a local2500ms lock budget guard writes. Native two-connection checks preserve an older read snapshot across committed retirement and observe retirement on the next read; concurrent initialization and receipts pass. |
| Optional schema and cleanup | Read-before-initialization stays read-only. Fact, lifecycle and use schemas initialize inside owned write transactions; type/key/index and expected cleanup-trigger/function checks reject tested malformed layouts. Native tests exercise missing index, disabled trigger, SECURITY DEFINER replacement, wrong receipt type and support TRUNCATE. This is bounded schema recognition, not arbitrary-DDL or malicious-owner attestation. |
| Evidence, lifecycle and identity | Full quote, null confidence, caller-attested truth scope and source-bound identities are preserved. Native and process tests exercise exact supporting quotes, explicit contradiction/supersession/retraction, promotion retirement veto, archive/restore, selected lifecycle batches, expiry and existing evidence validation. No inference becomes user truth automatically. |
| Receipts, paging and batch atomicity | Independently written processes create a receipt and race four identical reports, producing exactly one new row. They compare complete receipt rows before/after rejected batch application, not only counts. An attached support changes revision, invalidates the old selected batch and page snapshot, and leaves old receipts historical. A new batch commits both facts, its spent snapshot is rejected, and withdrawn usage cannot be reactivated. |
| Forgetting without collateral deletion | Independent calls archive/restore, forget one of two supports, verify revision progression and preserved historical rows, and replay a forgotten fragment. Removing final support deletes matching fact/evidence/archive/use rows while an unrelated supported fact and receipt survive. The final independent support is then forgotten and derived tables are empty. Native tests also check relation and TRUNCATE cleanup. |
| Native availability and retained regression | Actual Windows and Linux PostgreSQL servers, fresh complete programs and old native/context/session tests were run. Original full55-step/Windows60 qualification remains separately bound to identical runtime4f8b470f; it is not misrepresented as a newly rerun55-step suite in the supplement. |

The review examined the PG helper, FactStore integration diff and initialization,
public FactStore interface, use-receipt and batch logic, full original PG fact test,
original CLI/MCP test and both qualification workflows. The new process reviewer
imports no product, original fixture or oracle module; it derives event/item/fact
identities using independent canonical JSON and SHA256. It uses explicit checks
under both normal Python and -O and records request/output/error bytes and exits.

The new page-refusal check recognizes the fact_usage_ error family; the original
native suite independently requires exact fact_usage_snapshot_conflict. These are
not falsely presented as two identical assertions. Failure/counterexample commands
remain expected negative outcomes, not tests omitted from the report.

## Actual execution and counts

Original runtime run36558149579 completed both native jobs successfully. Its full
workflow retains Windows60, core tests,55-step accounting/lifecycle/application
regression and prior N48O/P checks. The original reports are historical qualification
of the exact unchanged runtime, not freshly replayed archive evidence this turn.

New run36647177198 at28d64ae7 completed all three jobs successfully on attempt1:
Linux109673779812, Windows109673780089, sanitizer109673780019. Full decoded job logs
were fetched and reviewed, including commands, structured outputs, counts and
binary/script identities. Actual native servers were PostgreSQL16.15 on Ubuntu24.04
and PostgreSQL14.24 on WindowsServer2022; this is not an exhaustive version matrix
or execution on the owner's Windows11 computer.

| Fresh supplementary gate | Actual result |
| --- | --- |
| Native facts | Each platform228 assertions:83 SQLite,145 PostgreSQL/setup. |
| Existing native context/session/scope | Each platform198 context,122 memory,112 relation-scope checks pass. |
| Core CTest | Six groups pass on each platform. |
| Original fact CLI/MCP differential | Each OS and Python mode105 recorded calls/304 checks pass; includes SQLite and realPG, with exact MCP permission negatives. |
| New independent SQLite review | Each OS and mode41 product calls/123 checks pass. |
| New independent PostgreSQL review | Each OS and mode64 recorded calls/174 checks pass:41 product calls,23psql. No fallback SQLite DB is created. |
| ASan/UBSan | Fresh Clang build with PG disabled:83 new SQLite checks plus15 original scenarios/380 assertions pass. Both captured stderr files are empty. No PG sanitizer execution is claimed. |

Windows EXE SHA256 reported by the new native job:
ce50003b8a93b75b84f281340f9f3068e22f284eed16eb17f6c8f46d094e93dd.
Linux executable SHA256 reported by its new native job:
dec7d42d9147b14730df1cbcb4be8d093dca0a6192a641a05a62d81e47c6e8ba.
Reviewer source identities are platform-specific and recorded in RESULT.json.

The local terminal and Python execution tools failed before running commands this
turn. Consequently no local build, ZIP extraction, full artifact replay, CRC check
or locally recomputed artifact SHA256 is claimed. Native CI performed the actual
execution; GitHub artifact metadata and job-recorded digests identify its archives.
The source pin and pre/post Git comparisons are executed runner checks, not an
independent offline reconstruction of every archive entry. No additional report-
mutation rejection counts are invented. Raw artifacts are retained for further
inspection and download with their actual qualification identity.

## Actual failures and corrections

The first supplementary run36646969799 at55517ba6 passed the substantive native
review but its sanitizer command omitted --sqlite-only. That test explicitly requires
a PostgreSQL test environment unless SQLite-only mode is selected, so the PG-disabled
sanitizer job failed. Commit28d64ae7 corrects the invocation flag, not the product,
assertions or time budget. A new full three-job run passed; the old failed run and
sanitizer artifact11069350312 remain recorded. This is a workflow configuration
error, not a newly discovered runtime memory vulnerability. No failed job was
rerun and relabeled successful.

Earlier4f8b470f corrects a malformed MCP permission fixture and replaces only the
obsolete PG-facts-unsupported expectation with exact authorized empty-report/no-DDL
behavior. Those inherited corrections are identified separately; their original
local failure files are not claimed newly downloaded or reviewed here.

During documentation assembly an incorrect copied historical blob identifier was
rejected by GitHub with422 before a tree/branch update. The file was fetched again
and its actual blob ID used. No runtime, test or accepted evidence changed.

## Limits, rollback and closure

Same DSN with another brain label is not tenant isolation; logical source is not
RLS. SQL schema owners are trusted. The4096-per-fact receipt limit, full-set pagination
and explicit batch semantics remain bounded product rules, not unlimited throughput
or complete whole-database validation. Historical statement versions and explicit
receipt reports do not authenticate user truth or actual model/host consumption.
Forgetting does not securely erase server WAL, backups or external copies.

No owner database, real user conversation, paid model or signing credential was used.
The synthetic test-role password belongs only to disposable loopback CI databases.
SQLite remains default, permissions do not automatically expand and no public
Release, old fixed ZIP or installer is replaced. Raw CI archives include programs
and evidence but are not an installer or dependency bundle. Windows/libpq and VC
runtime dependencies must come from trusted sources.

PG Hook integration, other remaining requirements, actual client lifecycle and
representative model quality/full-pipeline cost, complete DLP/RLS, signing/stable
release and Issue40 remain separate gates. Closing this module does not mark the
whole project complete or narrow its original requirements.

Only documentation, historical copies and executed-result indices are added after
qualified28d64ae7. Before merge, compare the closing commit with28d64ae7 to confirm
no runtime/test/workflow changes and use an expected-head normal merge. This scoped
acceptance is the reviewer's engineering judgment, not an absolute defect-free
warranty or third-party approval.
