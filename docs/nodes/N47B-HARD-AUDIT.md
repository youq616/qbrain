# N47B outcome review — paired conflict inspection

Verdict: **PASS for the scoped N47B implementation**. Reviewer: ChatGPT,
separate engineering self-review under the owner's latest explicit instruction.
Not an independent subagent or third-party audit. Original N47A subagent reports
remain unchanged; their conclusions are not reused as approval of this new code.

## Identity and stage boundary

Baseline: b4fc453a22c20597f99e1d2dfa9713cfeb2704c4.
Reviewed/tested product: 7999d39b9e6a253d62557a6ccc8341598ccdebb6.
Reviewed tree: cb00297d74efb890677f14a5dfb3e4976b9b29c9.
The 719 archived source files were recovered and the complete Git index rebuilt;
its tree hash exactly matches the candidate. No production, test, workflow or
package bytes were changed during this outcome review.

N47B implements FactStore::conflicts, `fact conflicts` and existing
`memory_read(view=conflicts)`. It does not implement automatic semantic conflict
detection, truth scoring, conflict resolution, decay, profiles or all of N47.
PR #17 is the integration location; the GitHub PR state determines merge status.

## Plan-by-plan outcome

| Requirement | Review and executed evidence | Result |
| --- | --- | --- |
| Only explicit contradictions | SQL selects contradicts edges; differing values alone return no pair; no inferred winner | PASS |
| Complete live endpoints and original evidence | Both loads reuse N47A role/source/hash/extraction/expiry validation; outputs retain full quotes, revisions, confidence=null and untrusted_data | PASS |
| One coherent read snapshot | Outer SELECT remains at SQLITE_ROW during both loads; real second WAL connection commits forget from a trace callback, first result retains both old endpoints and next call returns none | PASS |
| No half pair under output limits | 1..50 pairs and 512..32768 payload bytes; exact-size and one-byte-short tests; non-fitting complete pair stops the ordered prefix | PASS |
| Work/candidate bounds | 100 candidates plus sentinel; shared 512 evidence-check/8MiB budget; truncation flags distinguish incomplete results from no conflict | PASS |
| Source and endpoint filtering | Bound source/predicate/IDs, either endpoint, intersected filters, canonical IDs and no cross-source traversal | PASS |
| No hidden writes or authorization expansion | Denying SQLite authorizer, unchanged schema/revisions/jobs; MCP source denial and write-default-deny; six tools unchanged | PASS |
| History/evidence invalidation | Explicit retract/supersede, one/last support forget, tamper, wall-clock expiry, soft/hard deletion, next-call invalidation | PASS |
| Strict public entry points | Reject query/event/history fields for this view, malformed values, wrong MCP types and duplicate CLI options | PASS |
| Existing regression and delivery gates | 50 named native groups, all original fact/CJK/queue/HTTP/memory/Hook/PowerShell checks, exact-source reports before packaging | PASS |

This is a snapshot of explicitly recorded assertions, not proof either endpoint
is true. A forget committed during an existing read cannot withdraw bytes already
read; it is visible on the next call. The snapshot experiment uses two real
connections with a deterministic interleaving in one thread, not an invented
parallel worker or a timing-only concurrency claim. SQLite documents isolation
between separate connections in the same thread as well as between threads:
https://www.sqlite.org/isolation.html
https://www.sqlite.org/lang_transaction.html

## Original native runs and downloaded evidence

Development run 34798495285 completed source, portable, Windows full build/tests/
package, and same-source Server 2022 HTTP plus conflict unit checks successfully.
N42 run 34798495355 also completed successfully. The two generic publication jobs
were skipped, as designed; they are not evidence of a published N47B Release.

- Windows full registry: 50 groups, with real PostgreSQL DSN tests explicitly SKIP.
- Conflict unit on Server 2025, Server 2022 and portable: 13 scenarios / 346 assertions each.
- Actual conflict CLI/MCP on Windows and portable: 38 checks / 75 commands each;
  71 expected exit-0 commands and four expected negative exit-1 commands.
- Existing fact unit: 15 scenarios / 380 assertions; fact process: 34 checks / 118 commands.
- HTTP wire: 81 checks on each Windows job; fixed lifecycle controls/current
  repeats and explicit cache shutdown all passed without threshold changes.
- CJK: 72 unit checks and 36 process checks; queue: 40 scenarios / 776 assertions.
- Embedding unit/wire/search: 65/26/11. Memory/MCP/hooks/context/local config: 44/17/69/65/6.
- PowerShell 5.1 and 7 each: install 69, consent 16, transport 8.

Downloaded five original artifacts and checked their externally recorded SHA256,
archive bounds/CRC/member identities, exact package inventory, original report
bytes, source/EXE/script binding, full unit scenario names/assertion sums, process
exits, registry log and both HTTP schedules: **134 readback checks passed**.
Unit probe executables were not downloaded separately: their identities come
from the fixed original reports; the original same-source packaging job checks
the actual probe files. This limitation is not relabelled as an independent
probe-binary readback. See n47b-evidence/SUMMARY.json for IDs and digests.

Original inner ZIP: 1,924,291 bytes, SHA256
ceb1ad45109a1cdf7a5f72a4982465613ac4119c479025f6e45b139f01014e0c.
EXE: 3,906,560 bytes, PE32+ AMD64 with no embedded certificate, SHA256
cbe57072f6a63706a9e46fe26bfeacb3c324f5fcc05e36da1f4eff01f7a500e4.
The ZIP and executable were not rebuilt for delivery or repacked. They remain an
unsigned development candidate until separate, explicit reviewed promotion.

## Supplemental outcome-pass execution

Rebuilt the unchanged archive using Clang 17 with AddressSanitizer and
UndefinedBehaviorSanitizer for both bundled SQLite C and application C++, with
halt-on-error enabled. The production executable and standalone conflict tests
compiled. All 13 scenarios/346 assertions and the real 38-check/75-command
CLI/MCP schedule passed without a sanitizer diagnostic or unexpected child exit.
This is Linux instrumentation, not native Windows sanitizer or whole-program
security verification. No real host, provider, user brain or credentials used.

The archive-only local Git index has no HEAD commit. The local process report
therefore correctly records source_commit=null, not a made-up attribution; its
source bytes were independently bound by reconstructing the archive tree above.
The native CI reports, separately checked, retain their actual clean commit.

Also reran report-gate suites: conflict 10, fact 12, CJK 10, HTTP lifecycle 14 and
native registry 12 tests, all exit 0. Their synthetic failure outputs are expected
negative fixtures, not hidden product failures. No assertions were removed.

## Findings, limits and disposition

No unresolved P0/P1 defect identified within the stage scope. The following are
explicit nonblocking limits rather than hidden claims:

- The first oversized pair can prevent later smaller pairs from appearing; use
  filters or a larger budget. Empty plus truncated is not proof of no conflicts.
- Candidate/output limits do not bound total SQLite rows examined or OS latency.
- Malformed direct-database records may fail a read closed. Local hashes do not
  defend against an actor able to rewrite the database and recompute all hashes.
- Default-source permissions and existing fact evidence limits are inherited.
  The N47A P3 register remains open; this stage is not their blanket remediation.
- CLI help now explicitly says writes read JSON stdin, addressing the earlier
  help ambiguity without changing input behavior.

The known initial implementation link dependency issue was repaired before
7999d39b by using the established fact-test dependency closure. The outcome pass
needed no product correction. No failed native N47B run was retried to obtain a
passing sample. Transport/network code and fact schema are unchanged from N47A.

Stage code may be integrated and its exact tested package promoted. Promotion
must use a versioned non-latest preview, verify all original reports and assets,
and not enable general unreviewed auto-publication. No database downgrade needed
for source rollback. Whole-project, PostgreSQL parity, real-model quality/cost,
new signed-in host and signed production-release acceptance remain unclaimed.
