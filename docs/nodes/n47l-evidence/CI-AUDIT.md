# N47L repaired candidate — independent CI evidence audit

**Verdict: PASS within CI and artifact-readback scope.**

Auditor: `/root/ci_handoff_audit`, a separate subagent from the implementation
coordinator. Final live metadata and log inspection: **2026-09-17 14:05:59 UTC**.
This receipt does not replace the separate CLI, storage, report-gate, or outcome
code reviews. No GitHub comment, code mutation, push, merge, product execution,
signing, or publication was performed by this auditor.

The earlier candidate `1118e0faf5b7acdd3f27f933c801b4a2b1278d41` is not used as
acceptance evidence for this repair. Its green CI did not detect the CLI value
parsing and command-history validation issues identified by the code reviewers.

## Fixed source and completed workflows

- Candidate: `17e9a435f94e45b3ca22d3da062ba4683c135c4b`.
- Git tree: `f9d42819772df53dd8c6337c3cb19c8940d7023a`.
- Source archive: **883 files**, complete Git tree recomputed from the artifact;
  ZIP commit comment and fixed metadata also identify the candidate.
- Last PR readback: [PR #28](https://github.com/youq616/qbrain/pull/28), open draft,
  same candidate head; base `d033bdb23ae483a9bc68893ce1bb32c77d76fb28`.
  No parallel head update or PR discussion comment was observed.

| Evidence | Exact job | Result |
|---|---|---|
| N44 native Windows, full regressions and packaging | [105225444219](https://github.com/youq616/qbrain/actions/runs/35228307025/job/105225444219) | Success; every required step completed successfully |
| Server 2022 HTTP and unit suites | [105225444182](https://github.com/youq616/qbrain/actions/runs/35228307025/job/105225444182) | Success |
| N44 portable production processes | [105225444139](https://github.com/youq616/qbrain/actions/runs/35228307025/job/105225444139) | Success |
| ASan/UBSan production processes and unit suites | [105225444015](https://github.com/youq616/qbrain/actions/runs/35228307025/job/105225444015) | Success |
| N44 exact source archive | [105225443804](https://github.com/youq616/qbrain/actions/runs/35228307025/job/105225443804) | Success |
| N42 independent native full regression | [105225443301](https://github.com/youq616/qbrain/actions/runs/35228306922/job/105225443301) | Success |
| N42 portable CTest | [105225443442](https://github.com/youq616/qbrain/actions/runs/35228306922/job/105225443442) | Success; all 3 CTest cases |

Both runs were frozen only after final `completed / success` status:
[N44 run 35228307025](https://github.com/youq616/qbrain/actions/runs/35228307025)
completed at metadata update `2026-09-17T14:03:52Z`; [N42 run 35228306922](https://github.com/youq616/qbrain/actions/runs/35228306922)
at `2026-09-17T13:51:02Z`. Both are attempt 1 and identify the same source/tree.
The two N44 publication jobs were deliberately **skipped** by the workflow.

## Actual test and evidence results

| Platform | N47L unit | N47L CLI/MCP process |
|---|---|---|
| Native Windows | 16 scenarios / 258 assertions | 112 named checks / 126 commands |
| Server 2022 | 16 scenarios / 258 assertions | Not run by this platform's workflow |
| Portable | 16 scenarios / 258 assertions | 112 named checks / 126 commands |
| ASan/UBSan | 16 scenarios / 258 assertions | 112 named checks / 126 commands |

The native and portable N47L report-gate suite ran **20 tests, all OK**. Its
deliberately generated synthetic FAIL fixtures are negative validator tests,
not failures in the production process run. The original recall unit suite
remains **15 scenarios / 330 assertions**.

Both independent native logs were matched against the fixed source's actual
registry: **60 unique expected groups matched 60 unique PASS groups in N44,
and the same complete 60 groups in N42**. The receipt is not based only on a
reported total. The package summary was also checked against every original
report validator's returned counts, including all retained old suites.

The offline verifier completed **1,094 explicit readback checks**, including
all seven external artifact sizes/digests, source comment/tree and local source
bytes, both native registries, every required new/old report validator, installer
and legacy evidence, and the original package inventory and bytes. All validators
ran in an isolated Python child using only the authenticated archive source.

The package has **73 manifest members**, determined from the fixed packaging
source AST. Every source attachment matches the authenticated source bytes or
the sole permitted native Windows CRLF checkout transform; every evidence JSON
matches the original Windows artifact bytes. This includes the newly required
`verification/validate_multiterm_report.py` dependency. Manifest hashes, sizes,
summary, package checksum, and ZIP CRCs all matched.

## Immutable output identities

| File / object | Bytes | SHA-256 |
|---|---:|---|
| Original `qbrain-windows-x64-development.zip` inside the CI artifact | 2,114,341 | `ed44a43d79e1e76efa768e74872223cd5d867dfb92881fe67aab129789cd4408` |
| Original package `qbrain.exe` | 4,068,864 | `0bf0a19edcc672b750790016ed0979e001529a46d91def8f7d8b9bdffd8aae69` |
| `CI-METADATA.json` | 27,140 | `e3d4ebcf21131b6cfa891b0af2c3a72f10343986a142f2de5cd8a9f95b0832df` |
| `READBACK.json` | 81,068 | `016bdd09c7c51d45c067e4e725438a3fe1f0b481da572062910e40639473e2c0` |
| `verify_candidate.py` | 33,622 | `5a8f793b4f0054d55ffff0a134b013c770f3c686974c47dd46d57fd951ee80c6` |

Artifact IDs: source **10499777695**, Windows evidence **10501710021**,
original package **10500874382**, Server 2022 **10500761185**,
portable **10500153030**, sanitizer **10500261264**, N42 Windows **10500242901**.
Their exact names, sizes, hashes, run/source ownership, and latest-attempt job
snapshots are in `CI-METADATA.json`. The metadata SHA-256 above is a fixed
external pin, not a claim that an arbitrary JSON document is GitHub-signed.

The verifier itself received a separate read-only review from
`/root/ci_handoff_audit/verifier_inventory_review`. JSON overflow-float handling,
retrieval retention integer validation, and Windows ZIP path aliases were fixed
and rechecked before its final scoped PASS. The trust-boundary regression suite
ran **14/14 successfully against this repaired candidate's actual artifacts**;
its actual output is archived byte-for-byte as `verifier-new-candidate-tests.txt`, with its fixture pins and
command recorded in `verifier-tests-provenance.json`. It does not run qbrain.

## Explicit limits

- The product is unsigned. No live logged-in host/model consumption was claimed.
- Both complete native registry logs explicitly retain `SKIP-PG`: PostgreSQL
  integration tests were not run because no test DSN was provided.
- Server 2022 coverage is HTTP and dedicated unit suites, not a second complete
  production CLI/MCP process run.
- Unit-test and HTTP-probe binaries are not separately attached to these evidence
  artifacts. Their report hashes were validated structurally; only the packaged
  production `qbrain.exe` was independently rehashed here.
- The verifier neither executes the product nor republishes/rebuilds its bytes.
  Code-review closure, final live metadata recheck, merging, and release decisions
  remain with the coordinator under the owner's authorization.

## Archival layout and reproduction

The repository archival filenames are `CI-METADATA.json`, `READBACK.json`,
`verify_candidate.py`, and `VERIFY-README.md`. The README documents the exact
offline CLI and metadata schema. All SHA-256 values above refer to the original
file bytes; renaming for this layout did not serialize or change JSON bytes.

Original scratch receipt directory:
`/workspace/scratch/8ee4dd18bee0/n47l-evidence-tool/new-candidate/`.
Its `candidate-metadata.json` and `candidate-readback.json` are the byte-identical
inputs copied to the repository names above, and `artifacts/` holds all seven
outer CI ZIPs. The source used by this auditor was the separately authenticated
`/workspace/scratch/8ee4dd18bee0/n47l-evidence-tool/source/` snapshot.
