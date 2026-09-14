# N47D outcome review — opt-in Hook fact context

Verdict: **PASS for repository implementation and scoped native validation**.
Reviewer: ChatGPT, a separate engineering self-review pass authorized by the owner.
Not an independent subagent or third-party audit, nor a guarantee of no latent bugs.
Actual signed-in client consumption remains NOT_RUN and has a separate local task.

## Identity

Baseline: 984707be084591b2251701e29392c9a85e4c7c2f.
Tested/reviewed product: 5275045c4790b802b620ba0af52ec6248cd587d5.
Source tree: 7cd4ab256aa8dd885a95c00f8de712512933421a.
Original source archive: 745 files; reconstructed Git tree matches exactly.
All 300 production/test/build/dependency files compared with the local execution
source match byte-for-byte. Administrative source transport is not in the product.
No production, test, installer or workflow changes were made during outcome review.

## Acceptance against the approved plan

| Requirement | Observed implementation and execution | Result |
| --- | --- | --- |
| Explicit default-off consent | -EnableFactRecall, strict fact_recall boolean, Status, reinstall without flag and reversible uninstall on PS5.1/7 | PASS |
| Capture and recall independent | Capture-only, facts-only, both and neither tested; no new MCP write/provider consent | PASS |
| One complete fact neighborhood | N47C direct counter-evidence preserved even without matching terms; no truth winner or automatic fact creation | PASS |
| Unified serialized output | Facts first, then ordinary memories; complete hookSpecificOutput JSON including escaped payload is within recall_bytes; one max_items count | PASS |
| No single-memory bypass | Same-source attached items or exact quotes of existing facts, including retired facts, are suppressed from ordinary lane | PASS within stated per-event scope |
| One coherent read snapshot | Explicit read transaction spans both lanes; deterministic second WAL connection commits forget during read; next call observes it | PASS |
| Bounded and relevant retrieval | One fact call with up to eight unique terms and shared evidence work; recent enumeration only at SessionStart; no-term prompt returns none | PASS |
| No stale fact dedup | Fact groups revalidated on each relevant event; ordinary-memory seen IDs remain separate | PASS |
| Privacy/error boundaries | Source/project gates, sensitive input, malformed opt-in, expiration/tampering/forget, no quotes/queries in state/trace, nonblocking outer Hook | PASS in fixtures |
| Compatibility | Default-off legacy Hook, public fact/recall/conflict views, 52 native groups and all retained gates | PASS |

The budget is for ONE serialized Hook response, excluding its final newline, not
the entire conversation or a tokenizer's context window. Windows main already sets
binary stdin/stdout mode, so newline conversion does not invalidate this byte bound.
The fact lane shares 512 evidence validations/8MiB work; the ordinary lane retains
its own existing bounded read behavior. Neither is a bound on total SQL rows scanned,
filesystem latency or all runtime work. Failure produces no partially built group.

Source hashes detect local inconsistency, not a same-permission adversary rewriting
all records and hashes. The untrusted-data label is not full prompt-injection/DLP
protection. Suppression is exact-quote based, not semantic equivalence. Old default
source permissions are inherited without expansion.

## Original native execution

Development run **34862423429** and N42 run **34862423691** completed all required
jobs successfully on 5275045c, including final Windows regression and packaging.
The two generic publication jobs were intentionally skipped and are not a Release.

- Full Windows registry: 52 exact groups. Real PostgreSQL DSN cases remain SKIP-PG.
- Hook composer unit on Server2025, Server2022 and portable: 13 scenarios/229 assertions.
- Actual executable Hook fixtures on Windows and portable: 52 checks/72 commands,
  all with expected exit 0. Claude/Codex event fixtures are not live client sessions.
- New installer opt-in checks: 33 each under PowerShell5.1 and7, with original EXE,
  installer/script/source hashes and exact shell-major verification.
- Previous facts15/380 and34/118; conflicts13/346 and38/75; recall15/330 and44/71.
- CJK72 unit/36 process; queue40 scenarios/776 assertions; embedding65/26/11.
- Memory44, MCP17, old Hook69, context65 and configuration6 process checks.
- Both Windows HTTP jobs: 81 wire checks and unchanged fixed cancellation/shutdown gates.
- Each previous PS5.1/7 suite: installer69, consent16, byte transport8.

Counts include nested assertions and reused scenarios; they must not be summed as
unique user tasks. The six-tool memory profile and negative write tests remain.

## Separate outcome execution

Built SQLite C and application C++ with Clang17 ASan/UBSan and halt-on-error.
The new unit13/229 and actual Hook process52/72 schedules passed with no sanitizer
diagnostic. Linux instrumentation is not Windows sanitizer or a live-host test.
Old memory/fact/conflict/recall process suites were separately rerun successfully.
Report-gate suites also passed: Hook facts12, facts12, conflict10, recall10, CJK10,
HTTP lifecycle14 and native registry14, totaling82 tests.

An independent expected-adjacency composer oracle exercised ten facts, explicit
edges, a separate equal-quote item and an unrelated ordinary memory. It checked
126 combinations of budgets/counts/state/adapter, 1178 assertions and176 actual
commands on GCC and again on sanitized builds. Expected graph membership came
from the fixture model, not from calling the implementation as its own oracle.
Repeating on two builds is not twice as many unique business scenarios.

Two deliberately broken temporary copies were compiled. Removing raw-lane
suppression failed `raw exact-quote copy cannot bypass facts`; removing the
serialized-budget guard failed `never split or fallback to a bound quote`.
Both exited1 as expected; original candidate bytes stayed unchanged. These tests
show those assertions catch the corresponding defects, not all possible bugs.
Local archive-only process reports correctly keep source_commit=null; source
identity was established separately by exact archive/tree and byte comparisons.

## Readback and retained harness failures

Downloaded five original artifacts, verified external digests before interpreting
them, checked CRC/bounds/inventories, original report bytes, exact scenario/count/
exit/source/script/EXE bindings, old registry and both HTTP schedules: **187 checks
passed**. Diagnostic probe EXEs were not separately downloaded; their hashes come
from pinned original reports and the original package job's actual-file checks.

Original inner ZIP:1960966 bytes, SHA256
89918f2ed6964b4051d4542b7cd2358406423b6f3111db202e92e89e043086e8.
EXE:3937792 bytes, SHA256
cc544211b06dd4439cb79c69bf5baab190b831c97c9b87d911c8373bac8d7489.
PE32+ AMD64, empty certificate directory; unsigned. No rebuild or repack for delivery.

The first supplemental oracle assumed init returned JSON, but the existing command
returns plain text. The harness was corrected without changing product assertions;
its failure log is retained. The first readback checker incorrectly required a
result=PASS field in the old context benchmark JSON, which has no such field. It
now validates that report's actual schema/counts and null quality/cost claims,
while preserving original byte equality and all strict status checks elsewhere.
That failure is retained too; no original report was rewritten.
One four-character source-transport transcription duplication was corrected before
requiring the unchanged external compressed digest and all old/new Git blob hashes.
It did not alter product bytes or weaken source identity. No native product run
was retried unchanged until green during this stage.

## Nonblocking limits and remaining host boundary

No unresolved P0/P1 defect identified in the reviewed scope. Per-event forget does
not mean global erasure of the same sentence: when all fact support is forgotten,
the fact row is removed; another independently captured, unforgotten equal quote
can remain an ordinary memory. The oracle checks this existing semantics instead
of claiming phrase-wide secure erasure. Retraction suppresses ordinary bypass
while the retired fact exists. Backups and past client context are not erased.

An oversized first group can prevent later groups from being emitted; truncated
output is incomplete, not evidence of no matching facts. No CJK segmentation,
automatic contradiction inference, truth scoring, new facts or profile/decay.
A stale package-script comment says51 while its enforced registry is52; this is
cosmetic and does not weaken the checked gate. No runtime edit is made just to
change that comment under already-tested source identity.

Opt-in sends additionalContext to the authorized client, which may send it to its
configured model. No extra Qbrain provider call is NOT proof of no external data
flow. Trace host_consumption_confirmed remains false: correct fixture output is
not proof that a signed-in client loaded it or that its model consumed it.
Official interfaces and snapshot semantics consulted:
https://code.claude.com/docs/en/hooks
https://www.sqlite.org/isolation.html

Repository implementation may be integrated and its exact tested package promoted
to a versioned unsigned preview. Real client validation must use isolated synthetic
projects and existing login, not real brains or a simulated-host PASS. The single
local runbook is docs/integration/N47D-LOCAL-ACCEPTANCE.zh-CN.md. No compiler,
GitHub write credentials, repeat source export or repeat code audit is required.
Whole N47/project completion and signed production readiness are not claimed.
