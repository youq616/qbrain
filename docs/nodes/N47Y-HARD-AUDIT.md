# N47Y outcome review — complete receipt-integrity module and MCP path

2026-09-20. **PASS for the approved receipt-integrity and MCP-completion scope;
no known unresolved blocking finding remains in that scope.** Not a guarantee of
zero defects, a stable-v1 acceptance or a real-client/model result.
Reviewer: coordinating ChatGPT in a separate engineering outcome review expressly
requested by the owner, not a separate subagent or third-party certification.

## Ordered scope and exact accepted source

Base main: ad31f404ba5ca94b15dc992bf9f219fa572ab167.
Original pre-implementation plan/review: d346cf8f8721d95b3a37ea2cfc90e37d1a37f03b.
Supplemental plan approved before the MCP repair: bfeed5150c00df8e94ee6ec4371f3894b09fa297.
Accepted product/test source: **67c82b2246cb71991f62c4a40a1e681388c998dd**.
Accepted tree: **9efd8e3c6a47f27f45e4a55520b3bfd66282043f**.
Fixed push/attempt1 run: **35510640800**.

The continuation found unfinished PR43 at39357bae. Instead of starting another
module, it inspected the actual implementation and initial successful native CI,
then independently exercised positive, persistent MCP calls. That exposed a real
adapter bug, so the earlier green candidate was not accepted as complete. The
original plan remains verbatim in n47y-evidence/APPROVED-PLAN.md; the explicit
MCP-COMPLETION-PLAN extends its two-header boundary by one narrowly scoped adapter.

## Delivered behavior and acceptance mapping

| Requirement | Reviewed implementation and executed evidence |
| --- | --- |
| One integrity rule across the module | Summary, pages, new report, duplicate report and revoke share storage-class/ID/revision/time checks.14 named corruptions ×5 paths reject without application row/schema/backup changes. Valid restored controls pass. |
| No hidden TEXT/BLOB duplicate identities | Scoped indexed probes detect exact byte-equivalent aliases; ID storage type and byte length are checked before copying malformed large IDs. Requested-ID lookup also checks source-wide cross-fact aliases. Seven combined source/fact/usage BLOB variants reject through actual MCP. |
| Preserve legitimate behavior | Baseline/new normal CLI results match byte-for-byte, including filters and snapshot continuations.4096 capacity, tombstones, current/old revision separation, source isolation and no automatic repair remain. Legal archived/retired/expired receipts remain withdrawable; last-support forgetting still deletes them. |
| Complete advertised MCP integration | Add exactly receipt_state and snapshot as String fields in the typed memory_read gate. Real persistent MCP validates all4 filters and full3-page traversal. Wrong types, unknown field, bad filter, absent cursor pair, stale snapshot and wrong view still reject without writes. |
| Revalidate while writing | Existing BEGIN IMMEDIATE transaction rechecks integrity before insertion/duplicate success or tombstone update. Three controlled competing-writer schedules reject newly committed corruption, then succeed after fixture restoration. Simulated UPDATE ABORT preserves the original receipt; a later authorized revoke works. |
| Bounded reads and unchanged authorization | Ordered bounded scan plus exact alias probes; no whole other-source scan, coercion or eviction. Existing source resolver, write default-deny, backend restrictions, fact eligibility and pagination budgets remain. Native/local negative and existing permission tests pass. |
| Native and regression gates | Final Windows/Linux123 integrity checks and72 supplemental checks pass, retaining usage75/page71 and every original process suite. New MSVC build/full60 registration log and Linux4 focused groups are verified from original artifacts. |

Three inherited production files change: fact_usage.hpp, fact_usage_read.hpp and
the two typed-argument entries in src/qbrain/mcp/server.cpp. Original FactStore,
CLI/operation names, Hook, installer/bridge, schema, old tests/build lists, ledger
and frozen inventory do not change. The original123/75/71 tests were not weakened
or replaced when the additional72-case MCP test was added.

## Independently found and closed product bug

The tool description already advertised receipt_state and snapshot, but the
separate typed MCP gate rejected them. The exact downloaded39357 Linux executable
SHA2565310a5016034af11bf7571384c3bb0226ca66085bb60ab9154a740989b5e1780 passed three
healthy controls and failed the next healthy all-filter request with invalid_argument,
field=receipt_state, message=unexpected argument. This failure required no database
corruption. MCP-REGRESSION.json retains the actual request/response and report hash.
An earlier exploratory corrupted-page call hit the same adapter error; it is not
mislabelled as the intended integrity rejection or as a harmless fixture failure.

The two-entry repair follows the separately committed completion plan. The same
supplemental test passes72 checks on the repaired local GCC binary, the actual
final Windows and Linux CI binaries, and an additional local run of the downloaded
final Linux binary. Normal and optimized Python both execute the final CI test.
The original old-candidate failure remains evidence of coverage, not a passed gate.

## Fixed native evidence and independent readback

Run35510640800 is push/attempt1; Windows106077821848 and portable106077821745 and
all required steps completed/success. Both compile the changed product. Windows
uses the actual published N47X baseline EXE; Linux separately builds fixed baseline
ad31 from a clean checkout. Neither baseline is presented as the repaired program.

| Per-platform executed test | Checks / evidence |
| --- | --- |
| New integrity regression |123 checks,156 commands,468 saved raw stdin/stdout/stderr files;14 report mutations rejected normally and with-O |
| Separate persistent MCP test |72 checks in both modes;8 CLI setup calls and65 MCP requests per run,7 successful page replies,38 integrity rejections |
| Retained receipt tests |75 usage checks/118 calls;71 page checks/111 calls/333 raw streams |
| Retained process suites |Facts34, context65, multiterm112, named arguments60, search226, Hook facts52, lifecycle batch40, memory44, MCP17 |
| Native/core suites |Windows fresh production build and60 registered groups parsed from the original log; Linux4/4 focused CTest groups |

Original final artifacts were downloaded and checked against GitHub metadata:
- Windows10605072390:16556984bytes; SHA256 d29f8ac056a83ef45170f7cf75df3b28557007b634daa41d0c7d0eda545d4a2c;835members.
- Portable10605051057:17415355bytes; SHA256 5f9ae2161d06a631df48affe7fc32121c1282e8ce31adf486f8b33eea3d649a8;839members.

ZIP CRC/path checks, source markers and1210-file canonical Git tree match67c.
Windows has identical membership/modes;1196 files differ only by exact LF-to-CRLF.
The three product blobs and both added test files equal the locally compiled/tested
source. Both actual binary digests and the separately compiled baseline digests
are preserved in SUMMARY.json. All original integrity/page raw-stream hashes and
source-owned semantic report validators were rerun on downloaded records. The
legacy context test has a summary, not individually retained raw process streams;
this review does not invent those missing records. PostgreSQL remains SKIP-PG.

A separate metadata checker verifies all72 ordered check names,65 request/response
IDs, actual four-state page content, continuation token/IDs, duplicate results,
expected errors and scope. It passes on all four native boundary reports. Twelve
mutations of real reports reject; restored controls pass. That checker is retained
as check_boundary_readback.py and was also run under optimized Python. It checks
supplied evidence consistency, not authentication or already-deleted test databases.

## Additional local work, limits and final merge decision

Local GCC product SHA25645228c49913915fd10761a1ea9a88ac2597241a44cd227161d686b6e880098b9
passed123 integrity,72 boundary in normal/-O, retained75/71, all9 original process
suites and4 focused CTest groups. It was built from verified source-file bytes in
an extracted tree without .git; no local Git checkout identity is fabricated.
The downloaded final portable EXE independently passed the72-case boundary run.
The Windows EXE was downloaded/hash-checked, not executed on the local Linux host.

Four query shapes were also compiled against the same local product SQLite3.46.1
static library: exact scoped searches use existing indexes without a temporary
sort. This is query-plan validation on a synthetic database, not a performance
benchmark. SQLite storage classes and transaction semantics were checked against
https://www.sqlite.org/datatype3.html and https://www.sqlite.org/lang_transaction.html .

Initial synchronous local build invocations timed out; a separately recorded build
completed successfully. Early local evidence-adapter errors concerning Python import
paths/platform flags were corrected to the actual source-owned report contracts;
original product tests stayed unchanged. These are not native product failures.
The real positive-MCP failure above was not reclassified as a fixture problem.

Controlled locks prove the observed results for those schedules, not every possible
interleaving or exactly when a remote process reached preflight. SQL ABORT simulates
a database statement failure, not physical disk failure. Corruption is deliberately
injected into disposable data, not evidence that normal writes corrupt user data.
The new bounded reader is not an audit of all arbitrary aliases or hostile schema,
index and trigger replacements. It performs no automatic data repair or migration.
Supplemental records retain decoded MCP messages, not raw framing byte streams.
Caller reports remain unverified attestations; no client/model, fee, PG, signing or
Issue40 root-cause result is inferred from this module.

The complete scoped module is acceptable for source merge. Closing files must be
only docs/history and already-executed evidence-review material over67c; compare
the final diff and actual merge tree. A later merge-triggered run is not assumed
passed in advance. No Release/tag is changed; public N47X binaries do not contain
this correction. Raw Actions artifacts retain their2026-10-04 expiry policy; Git
contains exact pins and derived records, not a claimed permanent raw archive.
