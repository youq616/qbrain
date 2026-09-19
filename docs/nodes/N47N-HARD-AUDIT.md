# N47N final outcome — closure repaired and reverified

Date: 2026-09-19 (Asia/Seoul).
**Verdict: PASS for the approved search-CLI and ledger-closure repair scope.
No known unresolved blocking finding remains in that scope.** This is not an
absolute absence-of-defects claim, full-project completion or release approval.
Reviewer: coordinating ChatGPT, in a separate engineering self-review explicitly
requested by the owner. No independent subagent, Claude Code or third party ran.

## Authoritative object, not the rejected closure

Base main: b530f361dc9c36cf23127cc2f3c584f3215fb890.
Accepted native candidate: c26ec5e512d9ba960b86c9ced5b9b4976b031f2c.
Accepted native tree: 2beda65c13421a995826c147aad606ea48d7f694.

The a587 product had passed its tests, but f2ba subsequently replaced the active
ops ledger with an archive link. N47N run 35362126565 failed n31_a_counts_mapping.
That later failure invalidated the earlier source-closure claim. The earlier
report/status/summary are preserved byte-for-byte as n47n-evidence/PRE-CLOSURE-*;
REJECTED-LEDGER.md retains the failed fixture. Neither an older green run nor a
'documentation-only' label is used to bypass the failure.

The canonical ledger is restored to inherited blob
495862c7a4c869bf349b90343f9e34767374792a, exactly equal to the N47M archive.
The original native assertion and frozen inventory are unchanged. The new
read-only preflight checks exact names, section membership, duplicates and
mapping. Its newline-normalization and BOM-removal mismatches were repaired in
prior branch commits; this review re-executed their tests on c26.

## Acceptance review

| Approved requirement | Executed evidence and conclusion |
| --- | --- |
| Search-only product change | Compared all inherited src/include/schema/tests/scripts files against the N47M source: only commands.cpp differs; the added search_arguments.hpp is the pure search parser. Other handlers, storage, ranking, MCP, consent and schemas remain unchanged. |
| Explicit literal boundaries | --query VALUE, --query=VALUE and -- delimiter preserve data; only parsed values/flags reach dispatch. Pure-parser, real CLI/MCP and generated input checks pass. |
| Error rejection before opening | Missing/unknown/duplicate/mixed/empty queries and invalid limits/modes are rejected with no fresh data root. Source routing, defaults and original errors are covered by real-process tests. |
| Valid ordinary compatibility | 22 current/baseline exit/stdout/stderr byte comparisons pass. New rejection of formerly ignored malformed input is intentional, not claimed compatible. |
| Restore documentation contract | Canonical ledger bytes equal the inherited archive; 19 negative/positive tests pass normally and with Python -O. Fresh native N31 reconciliation passes. |
| Byte-reader parity | Newly authored crosscheck_ledger.py compiles the exact n31a_ledger_rows function from tests/test_n31.cpp. In 356 synthetic cases there are zero false approvals; canonical input passes and the rejected closure fails both readers. The preflight intentionally rejects 108 duplicate-row cases that the native set reader deduplicates. |
| Retained native gates | Fresh fixed-source N47N/N42/N44 and ledger workflows all pass. Native logs and original artifacts are read back below; no assertion or publication guard is removed. |
| Separate outcome review | Code/fixture review, fresh builds, ordinary/baseline tests, generated grammar, sanitizers, deliberate mutations, native-report identity and artifact verification were performed by the same coordinator in this later pass. |

'Literal' controls CLI parsing, not the backend matching algorithm. Punctuation
alone may yield no results. No --source search option was added; --no-vector does
not disable separately requested LLM reranking. Existing valid integer clamping
and configuration defaults are retained.

## Fresh native evidence on c26 (all push, attempt 1)

- N47N: [35368994138](https://github.com/youq616/qbrain/actions/runs/35368994138).
- N42: [35368994139](https://github.com/youq616/qbrain/actions/runs/35368994139).
- N44: [35368994091](https://github.com/youq616/qbrain/actions/runs/35368994091).
- Static ledger: [35368994105](https://github.com/youq616/qbrain/actions/runs/35368994105).

N47N Windows and portable artifacts each contain 361 parser checks and 226
process checks / 302 calls, all passing. source.txt equals c26. Replaying the
report checker against the freshly executed local schedule passes 1,746 checks
per platform and rejects eight corrupted reports per platform. Only the synthetic
put --file path is normalized; argv, stdin, expected exits and output byte hashes
remain checked. The temporary filesystem assertions are executed tests, not a
claim that the reviewer later observed their already-deleted directories.

The N47N, N42 and N44 Windows logs each verify all 60 registered groups, including
n31_a_counts_mapping. Static ledger Windows/Ubuntu artifacts each verify 19 tests
and both normal and optimized CLI checks. Live PostgreSQL is still SKIP-PG.
N44's two publishing jobs are intentionally skipped; all required jobs succeed.
Its Server 2022 HTTP/unit, portable, original ASan/UBSan, both PowerShell versions
and source/object/package checks remain intact. Server 2022 did not run the full
N47N process suite; Linux sanitizers are not Windows memory instrumentation.

The unchanged n47l-evidence/verify_candidate.py passes **1,216 checks over seven
original N42/N44 artifacts** using fresh c26 pins. It reconstructs the exact
1,005-file Git source tree, verifies every mounted source file, all 73 package
manifest members and retained report/command/native-log contracts. Two N47N and
two ledger artifacts were separately downloaded and checked, for eleven distinct
original artifacts inspected in total. Their IDs and hashes are in FINAL-SUMMARY.

The metadata snapshot was normalized from actual connector run/job/artifact
reads on September 19, not a raw or signed API response. Missing job source/attempt
fields in the step-summary response were taken from the containing run, with
source independently checked in archives and logs. The offline verifier itself
did not requery GitHub, execute the Windows package or download probe EXEs.

## New local executions in this review

| Check | Actual outcome |
| --- | --- |
| Pure parser, GCC | 361 checks, exit 0 |
| Real search processes | 226/226; 302 calls |
| Search with ordinary baseline comparisons | 248/248; 346 calls, including 22 byte comparisons |
| Same search suite against original main handler | 20/226 pass; 206 overlapping failures; 252 calls; expected exit 1 |
| N47M compatibility regression | 67/67; 127 calls, including seven byte comparisons |
| Existing process suites | memory 44, context 65, fact 34, multiterm 112, MCP boundaries 17, local config 6 pass |
| Focused CTest | 4/4 groups pass |
| Generated grammar, GCC and Clang ASan/UBSan | 18,768/18,768 each; no sanitizer stderr |
| Deliberately broken parser variants | All four rejected: 1,570 / 3,970 / 95 / 1,660 failing generated cases |
| Ledger negative suites | 19 tests pass under both normal and optimized Python |
| New native/Python ledger-reader comparison | 356 cases, zero false approvals; 108 intentionally stricter duplicate rejections |
| Existing validator suites | 193 report tests, 10 MSVC manifest tests, 32 native-log tests pass |

These are Linux engineering executions on isolated synthetic data. Generated
cases and baseline failures overlap; they are not distinct features or bugs.
Mutations were compiled only in temporary include directories; production bytes
were rechecked unchanged. The baseline links the exact N47M commands.cpp against
the otherwise-identical product libraries; it is not a downloaded Windows build.
No full Windows-oriented suite is claimed to compile locally on Linux.

## Distinct bytes and remaining limits

| Object | SHA-256 |
| --- | --- |
| Local candidate | 4aeafbc4b468bce4d0cbb95e58602186f4972a1b372f1a11160a60d67d541c4c |
| Locally relinked N47M handler baseline | 220a1933c427bcfab0979aed1afd7d012b4cf367c09bd937609bd00a1ed709d5 |
| N47N native process EXE | dc81405131ae0a31135f4f550522c0690f27fdf9fe676fc73607bb9bde2ce10b |
| N44 packaged EXE, 4,077,568 bytes | c35fadde8c8356b7243bf0b34cfd5c836bda27bb46da87eddcc79c1031bf05b5 |
| N44 inner ZIP, 2,117,939 bytes | ec681a4599bf1b2a90f3848f5bf65b6d6a32e37254f32392d0709c43080b356c |

The N47N native and N44 package executables differ despite matching product
source; their evidence is not conflated. No new public Release/tag, user install,
real brain access, client trust override or provider request was performed.
Old N47L downloads still lack N47M/N47N fixes. PG, complete ACL/DLP, semantic
inference, decay/profiles, model quality/cost, host consumption/egress and signing
remain outside this acceptance.

## Closure changes and retained history

This continuation did not alter search product code: it verified c26, added the
separate byte-reader comparison, and corrected stale a587 completion pointers.
Canonical ledger, frozen inventory, test fixtures, production, build scripts and
workflows must remain byte-identical to c26 in the closing diff. The final audit
commit is not substituted for the actual tested candidate. Actual merge/tree
identity is recorded in PR #31, and merge-triggered CI is not predeclared passed.

Historical duplicate-main, punctuation fixture and report-helper corrections
remain in PRE-CLOSURE-HARD-AUDIT.md. The rejected ledger and newline/BOM repros
remain in REJECTED-LEDGER.md, NEWLINE-REVIEW.md and BOM-REVIEW.md. Local clone/DNS,
unsupported streaming invocation and one combined command timeout were not
counted as passing tests; subsequent explicit builds/tests have recorded results.
No new product defect was found in the final pass; no historical failure is erased.

Reproduce the additional review with:

```text
python docs/nodes/n47n-evidence/crosscheck_ledger.py --root . --report ledger-differential.json
python .ci/test_search_arguments.py --binary <candidate> --baseline <N47M-baseline> --report search.json
python docs/nodes/n47n-evidence/generative_review.py --probe <compiled-parser_probe> --report generated.json
python docs/nodes/n47n-evidence/mutation_review.py --root . --output mutation-evidence
```

The new comparison helper is Linux/GCC-or-Clang review tooling, not a product
runtime prerequisite. Existing Windows scripts remain the primary build path.
FINAL-SUMMARY.json and C26-RAW-REPORT-HASHES.json retain exact report and artifact
identities; local raw reports are not silently claimed embedded in Git. Original
CI artifacts remain available subject to their October 2 retention expiry.
The older build_metadata.py/RAW-REPORT-HASHES.json describe the historical a587
review, not this c26 snapshot. Use current explicit pins, not those old defaults.
