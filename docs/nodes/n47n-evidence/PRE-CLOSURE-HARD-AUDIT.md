# N47N outcome engineering review

Date: 2026-09-18 UTC. **Verdict: PASS for the approved source-repair scope;
no known unresolved blocking finding remains in that scope.** This is not a
guarantee that the software is defect-free, the whole project is complete,
or an updated public Windows package has been published.

Reviewer: coordinating ChatGPT, in a separate engineering review after development,
as expressly requested by the owner in this conversation. No separate subagent,
Claude Code or third-party reviewer was used. The reviewer checked source diffs,
ran separately authored tests, challenged coverage with deliberate mutations,
reproduced baseline failures and read back the exact native artifacts.

## Review object and immutable evidence

| Object | Identity |
| --- | --- |
| Main baseline | b530f361dc9c36cf23127cc2f3c584f3215fb890 |
| Plan approved before implementation | fa69035e3a579981b97eb02057809e2fce46034a |
| Product/test implementation | e59ab36a2add9afb2b8c2619425ef92ca6072e60 |
| Retained gate branch triggers | 9484f17ad7255f3c30332fca5d87528f4fc383a6 |
| Repaired native test setup; final tested source | a587e1751cedf83075e3ff9b78627c953e3b807a |
| Final tested source tree | 3c2b5ef5f1ce76d271f19e235f33703120d4891c |
| Production commands.cpp blob | 8af9f8d829f630cb17247bf65f3aebd54b5324ae |
| Pure parser header blob | 528f322d7cbfe869d02d2f27062f40df54b45d16 |
| Process regression script blob | 66d2b20f5ec4f7aac11e7c3f3ac0f57a777dc90e |

Product bytes did not change after e59; later commits add existing gate branch
triggers and repair the newly introduced standalone unit build setup. The final
review/status archive changes only documentation and docs-scoped review material.
It must not replace the source identity actually compiled in native CI. Merge
requires final docs-only comparison and PR/main head checks; the merge receipt
records the resulting tree and parents.

## Acceptance against the original plan

| Approved criterion | Actual evidence | Result |
| --- | --- | --- |
| Search-only change | commands.cpp has only an include, help line and cmd_search rewrite; new pure header. Other handlers, global helpers, storage, ranking, MCP and schema unchanged. | PASS |
| Explicit literal grammar | --query consumes one literal argv, including --; equals form works; delimiter tails keep subsequent switches and -- as text. | PASS |
| Strict failure before open | Unknown, duplicate, missing, mixed and empty syntax, invalid int/mode and bad brain identifiers are rejected on fresh roots without creating data directories. | PASS |
| Routing/default compatibility | Actual brain option only, environment/file/default precedence, option order, original empty limit/mode fallback and int clamp; 22 ordinary byte comparisons. | PASS |
| No accidental option activation | Pure tests inspect all parsed values/flags; real CLI/MCP tests cover option-shaped text and output/routing/limit boundaries. No new provider permission or altered ranking. | PASS |
| Native and original regressions | Fixed a587 N47N/N42/N44 required jobs succeeded; new native reports and all registered groups read back; original report/package gates retained. | PASS |
| Separate outcome review | New generator, GCC/Clang sanitizer checks, four deliberate parser mutations, baseline rejection and source/artifact verification; same coordinator, not an independent agent. | PASS |

The intentional compatibility change is explicit: formerly ignored unknown or
duplicate options, partially parsed/invalid integers and invalid modes now fail.
Single-dash words remain data. CLI literal preservation is not exact-substring
search; the unchanged backend may return no hits for punctuation-only queries.
No --source option is added. --no-vector is not a promise to disable LLM reranking.

## Native executions and raw report readback

All final required evidence uses a587, attempt 1, push events:
[N47N 35358824747](https://github.com/youq616/qbrain/actions/runs/35358824747),
[N42 35358824750](https://github.com/youq616/qbrain/actions/runs/35358824750),
[N44 35358824749](https://github.com/youq616/qbrain/actions/runs/35358824749).
N44's two publication jobs were intentionally skipped. No release was created.

Windows and portable N47N artifacts each record **361 pure-parser checks and
226 process checks / 302 calls**, all passing. Native source.txt equals a587;
script hashes match the exact source or Windows line-ending checkout. A separate
readback checks each argv/stdin/expected exit/output hash against the pinned local
schedule, normalizing only the fixture put --file path. It rechecks literal
CLI/MCP equality, errors and order/routing results: **1,746 checks per platform**,
plus rejection of eight deliberately corrupted reports on each platform.
Ephemeral filesystem assertions remain trusted executed-test evidence, not a
claim that the reviewer later observed those deleted temporary directories.

N47N, N42 and N44 Windows full-suite logs each contain the complete **60-group**
registry. The new standalone parser is additional, not falsely counted as a
61st registered group. Real PostgreSQL is explicitly SKIP-PG. N44 retains its
Server 2022 unit/HTTP tests, portable tests, original ASan/UBSan gates, both
PowerShell versions, source/object inventory and package report validation.
Server 2022 is not another full run of N47N's CLI process test.

The unchanged N47L artifact verifier was run with new explicit pins and passed
**1,193 checks over seven original artifacts**, reconstructing **982 source
files**, checking **73 package manifest entries**, original report semantics,
complete process sequences and the N42/N44 native registries. Separately, all
347 product/build/test files from the final source artifact matched the local
bytes used for review. The normalized metadata snapshot is assembled from
actual GitHub connector run/job/artifact responses, not a raw signed API response;
the offline verifier does not independently query GitHub. Probe binaries were
not individually downloaded, and it did not execute the packaged Windows EXE.

## Newly executed local validation

| Test | Actual result |
| --- | --- |
| Fixed parser standalone (GCC and dedicated CMake) | 361 checks, exit 0 |
| Fixed real processes with baseline compatibility | 248/248, 346 calls; includes 22 exact exit/stdout/stderr comparisons |
| Fixed real processes without optional comparison | 226/226, 302 calls |
| Same final process test on the main baseline | 20/226 pass, 206 overlapping failures, 252 calls, exit 1 as expected |
| Separately authored generated grammar (GCC) | 18,768/18,768, exit 0 |
| Same generated grammar (Clang ASan/UBSan) | 18,768/18,768, exit 0, empty stderr |
| Four deliberate parser mutations | All four compiled and were rejected: 1,570 / 3,970 / 95 / 1,660 failing generated cases |
| Prior N47M process/compatibility | 67/67, 127 calls |
| Original process tests | memory 44, context 65, fact 34, multiterm 112, MCP 17, config 6, embedding 11, CJK 36 passed |
| Focused CTest | 4/4 groups passed |
| Existing validation tooling | 193 report tests, 10 MSVC inventory tests, 32 native-log tests passed |

These extra executions are Linux engineering evidence, not Windows sanitizer,
live client or PG acceptance. The generator constructs expected query/value/flag
objects before serializing argv, rather than copying the production parser loop.
It exercises the real header through a small JSON adapter. Generated overlaps
are not 18,768 independent features, and baseline failures are not 206 distinct
vulnerabilities. Deliberate mutations exist only in temporary include directories;
the product header remains unchanged. Local full original Windows-oriented suite
is not claimed to build on Linux; its complete execution came from native CI.

## Findings and corrections, not erased failures

**Closed validation blocker:** source review found that build-tests-cl.ps1
-TestSources APPENDS to the canonical test driver. Passing a standalone main()
caused duplicate entry points. Actual initial push run **35357242409**, source
e59, Windows job **105639477439**, failed with LNK2005/LNK1169; its product build
had passed and the later full-suite step was skipped. Artifact **10552593400**
(1,451 bytes, SHA-256 c581c870342d91372e69cb2a2c0bfe31e9145e893e1061bf26a8b0831cf19ee8)
was downloaded and inspected. The a587 repair uses an independent CMake target;
the original full suite and script were not weakened. Final native logs confirm
both the new standalone target and the original full suite now pass.

**Corrected fixture expectation:** initial local result 245/248 incorrectly
required a hit for pure --. The test now explicitly compares with unchanged MCP
and expects the same empty array. The parser separately verifies the literal
bytes survive. No backend behavior or production assertion was removed.

**Corrected review-tool assumption:** the first readback draft required every
case to spawn a command; the final two filesystem snapshot checks intentionally
spawn none. The checker now permits that only for those exact pinned case names;
all command schedules and other ranges remain checked. Its final positive and
eight negative tests pass. This was a review helper defect, not a product bug.

Two transfer blobs with wrong hashes were rejected before any tree referenced
them; only the exact tested commands.cpp blob entered the branch. These events
and the initial pending checkpoint remain in REVIEW-FINDINGS.md and raw evidence.
There is no new unresolved product blocker found by this scoped review.

## Distinct executable/package identities

| Object | SHA-256 |
| --- | --- |
| Linux main baseline | ee78fc6666c35e031ebad5158bbf73ba5892478c0cf8016a5af8c6505a46a9f5 |
| Linux reviewed product | 4aeafbc4b468bce4d0cbb95e58602186f4972a1b372f1a11160a60d67d541c4c |
| N47N Windows process-tested EXE | 53f4b5df475df82aded032585fb05d6477bbe4cb9e30a005cecd1f20d099dcaa |
| N47N portable process-tested binary | a36fff1f52975fd8906f58891f91ec225ca523188c020dfd63c23f5f3c471033 |
| N44 packaged EXE (4,077,568 bytes) | 3acd54b0897739c7b0294e3befb0c3cdd178984f2f55322e9b7871128ef0d823 |
| N44 inner ZIP (2,117,967 bytes) | 45ab56dd8ba518e61ee52eb7ce0e2cbe2d85dc76483c2aa1a5ddac3e39a37346 |

Identical source does not imply identical EXE bytes across separate builds.
The new N47N native process test executed its own compiled EXE, not the N44
package's differently hashed EXE. N44's original gates cover that packaged build.
No Windows package was executed in the Linux reviewer environment.

## Reproduction, retention and merge boundary

The new parser/unit/process tests and docs-scoped probe/generator/mutation/readback
scripts are in Git. FINAL-SUMMARY.json and RAW-REPORT-HASHES.json pin results and
raw report identities. Full local raw reports/logs are in the conversation's
review evidence ZIP, not silently claimed as embedded in Git. Original CI
artifacts remain GitHub artifacts subject to their October 2 retention expiry.
The metadata helper reconstructs this recorded snapshot from verified archive
bytes; it is not a current online check, and its /mnt/data paths describe this
review environment rather than paths on the owner's machine.

```text
cmake -S .ci/search_arguments -B build/search-unit
cmake --build build/search-unit --config Release
ctest --test-dir build/search-unit -C Release -V
python .ci/test_search_arguments.py --binary <candidate> --baseline <main-baseline> --report search-process.json
python docs/nodes/n47n-evidence/generative_review.py --probe <compiled-parser_probe> --report generated.json
python docs/nodes/n47n-evidence/mutation_review.py --root . --output mutation-evidence
```

Build parser_probe.cpp with the production string_util.cpp, include/ and
third_party/ using C++20; the Linux review used GCC -O2 and Clang with
-fsanitize=address,undefined -fno-omit-frame-pointer. Python is test-only.
The artifact verifier in n47l-evidence uses source a587, tree 3c2b5ef5, the exact
N42/N44 run IDs above and metadata SHA-256
1d04fe3542d0fe0145e26608412bc6e5ddc4b8b7be42726868f3075477d2de9b.

This source scope is eligible for merge after final docs-only diff and current
head checks. No new Release/tag, installation, host trust override or real brain
change is performed. Old N47L download still lacks N47M/N47N fixes. Existing
project limits remain: live PG, comprehensive ACL/DLP, semantic inference,
automatic decay/profiles, model quality/cost, host consumption/egress and signing.
The previous README/status/inventory are archived byte-for-byte and linked from
the new current entry points. Passing this node does not finish the entire project.
