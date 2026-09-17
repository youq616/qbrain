# N47L final publication pin review

Reviewer: separate actual ChatGPT subagent `/root/recall_storage_review`, performing the owner's authorized engineering review.

**Verdict: PASS_FINAL_PINS_SCOPED.** The final workflow binds the completed review, merged PR, committed evidence and original CI package bytes correctly. No unresolved P0/P1/P2 finding was identified in this final factual-binding scope. This is not an assertion that publication has occurred.

The actual read-only checking program exited **0**, with **45 checks** passing. Its complete checks, final pins, normalized GitHub observations, all 49 changed documentation paths and byte hashes are recorded in [N47L-PUBLICATION-PINS-REVIEW.json](N47L-PUBLICATION-PINS-REVIEW.json). The 45 pin checks are separate from the historical 1094-check artifact verifier execution and earlier 11-case publication-control simulation.

## Exact final workflow and unchanged control logic

- Reviewed corrected template: [n47l-publish-template.yml](n47l-publish-template.yml), SHA-256 `aad1e079a252ce58dff3decebf95f040c46979530da75af3c9236d73cd7e651a`.
- Final concrete workflow: [n47l-publish-final.yml](n47l-publish-final.yml), SHA-256 **`389b6f38cf695e2f1ebfe149761e45ccd5b8dac35142f97e8ff1650991fe7a3a`**.
- Concrete manifest: [n47l-publication-pins.json](n47l-publication-pins.json).

I checked the full byte difference independently. There are exactly **11 environment-value substitutions** and replacement of the initial preparation comments. After performing those permitted substitutions in the reviewed template and excluding only the initial comments, all remaining bytes equal the final workflow. Both executable Python blocks are individually byte-identical to the reviewed blocks. The trigger, delivery ref, job permissions, action pins, CI/artifact gates, token handling, exact asset ID/digest checks, draft readback, publication target and failure behavior are unchanged.

The first filled-pin guard was actually executed under an audit hook denying network, subprocess and filesystem mutations; it returned 0. The publication block was parsed and compared but was **not executed**. The prior [publication-control review](n47l-publication-review.md) and its closed P2 finding therefore remain applicable; no publication control was silently relaxed during pin filling.

## Independently observed GitHub facts

Using the GitHub plugin's GET-only API, I independently fetched [PR 28](https://github.com/youq616/qbrain/pull/28) and the Git commit objects for the source, review and merge. These observations were captured at **2026-09-17 14:19:08 UTC**.

| Binding | Observed and verified value |
| --- | --- |
| Tested source | `17e9a435f94e45b3ca22d3da062ba4683c135c4b` |
| Tested source tree | `f9d42819772df53dd8c6337c3cb19c8940d7023a` |
| Reviewed documentation commit | `218482b5714a28cb8b27451310b8cafb6927076d` |
| Review tree | `babfb44341e5aec9576c3ccd84f88ac373871ebe` |
| PR 28 merge commit | `17aba70b73374fc39a0bb220f038ba11018b4b4a` |
| Merge tree | `babfb44341e5aec9576c3ccd84f88ac373871ebe`, exactly equal to the review tree |

PR 28 was actually `merged=true` and `state=closed`; its head SHA is the pinned review commit, its merge SHA is the pinned merge commit, both repositories are `youq616/qbrain`, and its base ref is `main`. GitHub records the merge time as `2026-09-17T14:16:41Z`. The review commit's sole parent is the tested source. The merge parents are `d033bdb23ae483a9bc68893ce1bb32c77d76fb28` and the pinned review commit.

Local Git object trees match the independently fetched GitHub trees. A full, zero-terminated, no-renames source-to-review diff contains **49 changed paths, all under `docs/`**; the source is an ancestor of the review. The committed review also contains the exact `aad1e079…` publication template. No product implementation or executable workflow changed in that documentation closure.

## Concrete pin values and evidence bytes

| Environment pin | Verified value |
| --- | --- |
| `REVIEW_SHA` | `218482b5714a28cb8b27451310b8cafb6927076d` |
| `REVIEW_TREE` | `babfb44341e5aec9576c3ccd84f88ac373871ebe` |
| `MERGE_SHA` | `17aba70b73374fc39a0bb220f038ba11018b4b4a` |
| `METADATA_SHA256` | `e3d4ebcf21131b6cfa891b0af2c3a72f10343986a142f2de5cd8a9f95b0832df` |
| `SUMMARY_SHA256` | `771de3746760513abffd7bc0c94543c13678629e54d4cd4b9c84c6dcec6f963d` |
| `VERIFIER_SHA256` | `5a8f793b4f0054d55ffff0a134b013c770f3c686974c47dd46d57fd951ee80c6` |
| `READBACK_CHECKS` | `1094` |
| `PACKAGE_BYTES` | `2114341` |
| `PACKAGE_SHA256` | `ed44a43d79e1e76efa768e74872223cd5d867dfb92881fe67aab129789cd4408` |
| `EXE_BYTES` | `4068864` |
| `EXE_SHA256` | `0bf0a19edcc672b750790016ed0979e001529a46d91def8f7d8b9bdffd8aae69` |

I rehashed the **committed Git blob bytes**, not just working-directory copies, of [CI-METADATA.json](CI-METADATA.json), [SUMMARY.json](SUMMARY.json) and [verify_candidate.py](verify_candidate.py) at the pinned review commit. All three match their final environment pins.

The committed [READBACK.json](READBACK.json) has SHA-256 `016bdd09c7c51d45c067e4e725438a3fe1f0b481da572062910e40639473e2c0`, matching the summary's recorded readback hash. Its result is PASS and its check count is exactly **1094**. Source/tree, metadata provenance, verifier hash, seven artifact identities, package size/hash and EXE size/hash agree across the final manifest, summary and readback. Native N47L report summaries agree with the workflow's explicit 16 scenarios/258 assertions and 112 process checks/126 commands.

The source and original workflow runs remain fixed at N44 **35228307025** and N42 **35228306922**. This pin check did not rerun the native tests, re-execute the 1094-check verifier or requery the CI runs; the unchanged publication workflow will requery the complete live run/job/artifact state before its first write.

As an additional direct byte check, I rehashed the locally retained original CI package artifact against its committed artifact digest and size. I then read the original `qbrain-windows-x64-development.zip` member directly, followed by its `qbrain.exe` member, without extracting or executing either. Their actual byte counts and SHA-256 values equal the final package/EXE pins above. No rebuild or rezipping was performed.

## Scope and remaining operational conditions

This check used read-only GitHub GETs, read-only local Git/object/file operations and a guarded execution of the first pin-validation block. No branch, tag, release, asset or repository file was created or changed by this reviewer; no push or publication was performed.

The outcome approves the exact `389b6f38…` final workflow's factual bindings to the already-reviewed control logic. A different workflow hash requires a new difference check. Live CI expiry/status, release absence, tag identity, original artifact bytes and draft asset identity still have to pass the workflow's unchanged runtime gates.

The documented remote non-atomicity limit also remains: publication may succeed remotely before a connection or later validation failure. This review does not convert separate GitHub requests into an atomic transaction or broaden “pre-publication failures retain the draft” to all possible failures.
