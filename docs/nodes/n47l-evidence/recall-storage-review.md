# N47L independent storage engineering review

Reviewer: a separate ChatGPT subagent (`/root/recall_storage_review`) performing the owner's authorized engineering review. This is not a Claude Code or independent third-party review.

Scope verdict: **PASS for the inspected N47L FactStore storage change.** No P0, P1 or P2 implementation defect was identified in this scope. This verdict does not approve the whole node, interfaces, CI reports or package promotion. The initial candidate had a separately discovered CLI option parsing regression; its repair and final acceptance belong to the independent interface review.

Initial reviewed/executed candidate: `1118e0faf5b7acdd3f27f933c801b4a2b1278d41`, relative to `d033bdb23ae483a9bc68893ce1bb32c77d76fb28`.

Final candidate binding: `17e9a435f94e45b3ca22d3da062ba4683c135c4b`, tree `f9d42819772df53dd8c6337c3cb19c8940d7023a`. The reviewer verified this exact tree with `git rev-parse` and a clean `git diff --exit-code` between the initial and final candidates for `src/qbrain/memory/fact_store.cpp` and `include/qbrain/memory/fact_store.hpp`. Their SHA-256 values still equal the hashes below. The intervening committed changes also leave session-memory validation, UTF-8 validation, storage, Brain and bundled SQLite unchanged. The existing 3415-assertion storage execution therefore remains applicable to this limited storage scope; it was not rerun or presented as a fresh execution on the final commit.

Read before review: `AGENTS.md`, `docs/nodes/N47L-PLAN.md`, and `docs/nodes/N47L-PLAN-AUDIT.md`. No implementation source was changed, committed or pushed by this reviewer. Temporary probe source, binary and output were created outside the repository.

## Code findings and acceptance coverage

| Concern | Evidence and assessment |
| --- | --- |
| Conjunction/disjunction applies to one anchor | `src/qbrain/memory/fact_store.cpp:730-747` constructs one candidate SELECT with each term tested against that row's `object`. The closed enum selects fixed AND/OR text. A direct independent oracle below exercises both modes, term repetitions, ASCII case, several scripts and punctuation. |
| Full input checked before split | `fact_store.cpp:681-686` validates the mode, nonempty input, original 1024-byte limit including separators, embedded NUL, scalar-valid UTF-8, ASCII-whitespace-only input and the existing sensitive-material detector. Only then do lines 689-695 split ASCII space/tab/CR/LF. Duplicate terms still consume the maximum of eight. |
| Per-term boundary validation | `fact_store.cpp:707-716` retains each term's nonempty/NUL/UTF-8/sensitive validation and aggregate bound. `include/qbrain/util/utf8_display.hpp:10-40` rejects overlong encodings, truncated sequences, surrogates and values above U+10FFFF. Sensitive matching reuses `session_memory.cpp:165-180`; this review does not claim a general secret classifier beyond that established detector. |
| SQL values remain data | Only fixed SQL fragments are concatenated. Source, every query term and optional predicate are bound at lines 745-747. The oracle includes `%`, `_`, `;`, single quotes and backslashes as literals. The parent unit tests' SQL injection/wildcard fixtures were also inspected. |
| Candidate cap follows matching | Matching, source/predicate and archive predicates precede `ORDER BY ... LIMIT 101` at lines 730-754. The separate runtime probe distinguishes this from fetching 100 recent rows and filtering later, including 101 newer rows that match only one of the two AND terms. Invalid supported rows still consume the bounded candidate scan. |
| Complete direct counter-evidence | Lines 762-790 traverse explicit direct contradicts edges without applying query terms or the anchor archive exclusion to counterclaims. Source, active status, user subject, predicate, bounded value and actual evidence remain checked. Canonical edges only; no recursive expansion. N47L archived nonmatching, neighboring-anchor and lifecycle unit scenarios were reviewed. The independent work-budget probe constructs 32 nonmatching neighbors with 16 supports each, forcing all direct evidence to be processed. |
| Retired/expired/forgotten evidence remains ineligible | Anchor SQL requires active status; counterpart eligibility repeats it. `load` and `evidence` at lines 198-278 check original quote, hashes, event/page state and expiry using one call time, with missing/invalid evidence omitted. N47L changes do not bypass these paths. Forget, expiry/tamper and supersession unit scenarios and inherited N47C wall-clock expiry scenario were inspected; this reviewer did not independently run the wall-clock expiry fixture. |
| Byte/result bounds never emit an incomplete group | Item insertion happens after the complete neighbor loop, at lines 791-798. Oversized items are removed as a whole. `fact_read_work_limit` is caught outside the in-progress item and marks truncation at lines 800-803. Existing exact-output and one-byte-short tests were reviewed; the independent probe exercises the distinct 512-evidence-check exhaustion boundary and confirms no partial star appears. |
| Work budgets/cache are call-local | A new `ReadWork` is allocated at line 748. The independent 528-support fixture exceeds the 512-check limit under both modes; each returns no item with `truncated=true` and `work_limited=true`. A subsequent fresh small recall succeeds without carrying over the exhausted work budget. |
| Snapshot covers schema and later reads | `ReadSnapshot` at lines 130-141 pins a read before archive/schema detection at line 720. The independent actual-two-connection WAL probe commits creation of the lifecycle module and archive entry during the first schema existence probe, before candidate selection. The first call still returns the pre-archive anchor, the next sees archive exclusion, and no read transaction leaks. This specifically tests an earlier interleaving than the unit's neighbor-read forget hook. |
| Read-only transaction behavior | The pin is a SELECT held at `SQLITE_ROW`, with no BEGIN/ROLLBACK or mutation in recall. The authorizer/caller-transaction unit scenario was reviewed. The independent runtime probe verifies implicit read transactions are released after normal results and work-limit failure. It does not independently install a write-denying authorizer. |
| Legacy public and Hook compatibility | The default/explicit literal call goes through the existing single-term internal path (line 687); the output's old match-mode values remain when the private mode is empty (line 723). Hook still calls the same private route with no mode (lines 699-700). This reviewer inspected exact-byte unit fixtures but did not build or execute a separate baseline binary. The additional validation changes the number of read-only validation calls, not the successful legacy JSON construction. |

## Independent execution evidence

Environment: parent-built GCC 13.3 Release static libraries in `qbrain/build/takeover`, with the repository's bundled SQLite. This is Linux portable engineering evidence, not a claim of running Windows/MSVC on this machine.

Probe: [recall-storage-probe.cpp](recall-storage-probe.cpp).
Actual execution log: [recall-storage-probe.txt](recall-storage-probe.txt). These colocated evidence files are byte-identical to the original temporary probe source and log.

The probe was written independently of `tests/test_n47l.cpp`, linked against the actual candidate libraries, and executed with exit code **0**. It uses real `capture`, local `extract`, `FactStore` create/attach/contradict/archive/retract operations and two real Brain connections; it does not substitute a mock store. Its 300 deterministic generated query strings each exercise both new modes against an independently calculated C++ ASCII-folded substring oracle, giving **600 query/mode cases**.

Actual output:

```text
differential: 600 query/mode cases passed
candidate cap: AND before cap and bounded invalid OR candidates passed
evidence budget: 528-support neighborhoods discard on 512 bound, next call resets
snapshot: archive schema created between initial snapshot and schema detection passed
Independent storage probe PASS, assertions=3415
```

The 3415 assertions include fixture evidence checks as well as behavioral assertions; they are not 3415 independent test scenarios.

Hashes recorded after the run:

| Artifact | SHA-256 |
| --- | --- |
| Probe source | `83674a86fe84d75695de5b48b63ee53739efb69d8b2a747044ffbb443c738e37` |
| Probe execution log | `b3d15ec5dc4b8773ff22fd71ae1949d3ae8721c321faa3ff81390f2e2cb4b3a1` |
| Original temporary probe executable | `833ffd6e78fe713a8537f57ab3b5f82be5532621eccbc167ecfb34594722cb12` |
| Candidate `build/takeover/libqbrain_memory.a` | `d4b0ac7f81453f87288236bd15a553c1a09bec167644adec02e88f0cfdb4379f` |
| `src/qbrain/memory/fact_store.cpp` | `e2576aa9dd8df080a62dc65d6f9838c2f23cc5f1134eff428c9c0d63701a8fe3` |
| `include/qbrain/memory/fact_store.hpp` | `f087da855253f1f31d1254d8464abefdb73fa5b79ad1935e3b1355a1945b85be` |

## Reproduction

From the repository root, the following Linux GCC/Clang commands build the actual project libraries and link the independent probe. They use the bundled dependencies and create all rerun outputs under `build/`; the recorded evidence files remain untouched. Prerequisites are a C++20 compiler, CMake 3.24 or newer, and Ninja. This command block is a reproducibility recipe, not a claim of an additional run during the final-candidate binding check.

```bash
cmake -S . -B build/n47l-storage-review -G Ninja -DCMAKE_BUILD_TYPE=Release -DQBRAIN_WITH_PG=OFF
cmake --build build/n47l-storage-review --target qbrain_multiterm_tests --parallel 2
c++ -std=c++20 -O2 -Iinclude -Ithird_party -Ithird_party/sqlite/sqlite-amalgamation-3460100 docs/nodes/n47l-evidence/recall-storage-probe.cpp -Wl,--start-group build/n47l-storage-review/libqbrain_*.a build/n47l-storage-review/libsqlite3.a -Wl,--end-group -o build/n47l-storage-review/recall-storage-probe
build/n47l-storage-review/recall-storage-probe > build/n47l-storage-review/recall-storage-probe.log 2>&1
cat build/n47l-storage-review/recall-storage-probe.log
```

Expected: process exit 0 and the five output lines shown above, ending in `assertions=3415`. Compiler/library changes can change binary hashes; the original binary hash is historical provenance, not a reproducible-build assertion.

## Limits and disposition

The storage implementation meets the reviewed plan constraints. No storage revision is requested. This review does not cover CLI/MCP option routing, JSON report validation, Windows build closure, GitHub workflow conclusions, release archive provenance or native deployment. The parent must combine this scoped review with the interface repair/review and actual validation/package evidence; this report is not a substitute for those gates.
