# N47L publication-control independent engineering review

Reviewer: separate actual ChatGPT subagent `/root/recall_storage_review`, under the owner's engineering review authorization. This is not third-party certification or Claude Code review.

**Verdict: PASS_SCOPED for the corrected publication template's inspected control flow.** One P2 asset-integrity defect was found, reproduced, repaired by another agent and independently retested. No unresolved P0/P1/P2 finding remains in this inspected scope. This report does not assert that a release has been created, uploaded or published, and does not certify the still-unresolved final review/merge/content pin values.

Reviewed fixed source: `17e9a435f94e45b3ca22d3da062ba4683c135c4b`, tree `f9d42819772df53dd8c6337c3cb19c8940d7023a`. Fixed workflow runs: N44 `35228307025`, N42 `35228306922`. The template fixes repository `youq616/qbrain`, PR 28, delivery branch `delivery/n47l-reviewed-17e9a435`, and release tag `multiterm-preview-17e9a435`.

Corrected template: [n47l-publish-template.yml](n47l-publish-template.yml), SHA-256 **`aad1e079a252ce58dff3decebf95f040c46979530da75af3c9236d73cd7e651a`**. Line references below refer to this 415-line template. The `REPLACE_*` fields deliberately remain unresolved; final concrete pins require a separate factual binding check before installing the executable workflow.

## Found defect and actual closure

**P2, closed — same-name, same-size release asset replacement escaped the last checks.** In the original 398-line template, `asset_metadata` at lines 360-366 only checked asset names, upload state and size. After downloading and comparing the draft bytes, the pre-publication and post-publication checks reused that incomplete metadata check. An intervening release writer could replace the package with a same-name, same-length asset; its new ID and digest were ignored. The workflow could consequently report `PUBLISHED` while the actual release package differed from the verified CI bytes.

The initial actual offline reproduction is preserved in [n47l-publication-asset-probe.json](n47l-publication-asset-probe.json) and its original [n47l-publication-asset-probe.py](n47l-publication-asset-probe.py). The control published the original mock package; the replacement case also published and returned `PUBLISHED`, despite different original and remote package SHA-256 values. These were offline state doubles, not real GitHub releases.

The corrected template freezes each local asset's size and SHA-256 at lines 334-337. Its initial draft check at lines 364-384 now requires exactly the expected names, unique positive integer asset IDs, uploaded state, integer byte sizes and matching `sha256:` digests. It saves the full name-to-ID/size/digest inventory. Both the last pre-publication check and public check require that same inventory at lines 393 and 402. The receipt records those pins.

The old bytes are available as [n47l-publish-template-before-asset-fix.yml](n47l-publish-template-before-asset-fix.yml), SHA-256 `96796d47fdf75a4e14dc181b0d2e3f9e3efcb6253e89eb81b03fa7a506d8e50a`. This file was reconstructed by reversing the isolated asset fix after the working template had been edited; its resulting bytes were verified to match the SHA-256 recorded during the initial review. It is not presented as an untouched contemporaneous backup.

## Independent offline execution

The reusable [n47l-publication-review-probe.py](n47l-publication-review-probe.py) extracts the supplied template's real helper definitions, fixed-local-asset initialization and entire publication tail. It substitutes only GitHub API/CLI/tag operations with controlled remote-state doubles. It executes the actual draft checks, download comparison, final checks and publication ordering. The fixture assumes the earlier CI gates produced the correct local assets; it does not mock a new CI acceptance result.

The identical **11-case** matrix was run against the exact old and corrected template bytes. Both runs exited 0 after checking their expected outcomes:

- [n47l-publication-review-before.json](n47l-publication-review-before.json): `REPRODUCED_INITIAL_DEFECT`, 11 cases, original template hash.
- [n47l-publication-review-after.json](n47l-publication-review-after.json): `PASS_EXPECTED_OUTCOMES`, 11 cases, corrected `aad1e079…` template hash.

| Case | Corrected template's observed outcome |
| --- | --- |
| Existing tag already points to the fixed source | Original assets read back; one publication PATCH; `PUBLISHED` receipt. |
| Tag initially absent | Creates only the fixed source tag; original assets read back; one publication PATCH. |
| Same-name/same-length different bytes replace the package after download | Rejects before publication PATCH; draft retained. This is the original P2 counterexample. |
| Same bytes/digest but a new asset ID after download | Rejects identity change before publication PATCH; draft retained. |
| Initial upload metadata omits a digest | Rejects before publication PATCH; draft retained. |
| Initial upload metadata duplicates an asset ID | Rejects before publication PATCH; draft retained. |
| Downloaded bytes are corrupted while metadata remains unchanged | Direct byte comparison rejects; no publication PATCH; draft retained. |
| A release already exists for the fixed tag | Rejects without creating another release or issuing a publication PATCH. |
| Tag changes after draft download | Rejects before publication PATCH; draft retained. |
| API GET fails during the final pre-publication check | Rejects before publication PATCH; draft retained. |
| Remote PATCH commits, then its connection fails | Local execution fails and emits no success receipt, while the simulated remote release is already public. This explicitly demonstrates the non-atomic limitation below. |

The last case is a limitation demonstration, not a successful publication guarantee. “11 cases” means 11 distinct state scenarios, not 11 real release attempts or a new native product test run.

Both Python `run` blocks were separately parsed and executed with unresolved pins under a Python audit hook denying socket operations, subprocess launches and filesystem mutations. [n47l-publication-guard-probe.py](n47l-publication-guard-probe.py) and [n47l-publication-guard-after.json](n47l-publication-guard-after.json) preserve the reproducible final check. The first block exited 1 with `Unresolved publication pin: REVIEW_SHA`; the publication block executed in isolation exited 1 on the unresolved readback-count value. Neither attempted a denied side effect. This is a check of the template's Python guards, not a claim that GitHub's own runner startup or action-download infrastructure performs no network I/O.

## Inspected publication boundaries

| Boundary | Assessment |
| --- | --- |
| Fixed source and execution context | Lines 43-64 validate all pin shapes and fixed source/run identities before checkout steps. Lines 170-189 repeat critical pins and require the exact repository/delivery ref, candidate commit/tree, review commit/tree and merge tree. Local full-history ancestry and zero-terminated full diff checks require source-to-review changes to stay under `docs/`. |
| Reviewed merge binding | Lines 190-193 require PR 28 to be merged and closed in the correct repository, with exact review head, merge commit and main base. Checking the merge tree against the review tree prevents unreviewed merge content from replacing the reviewed tree. |
| Reviewed documents and verifier | Lines 195-215 rehash the summary, CI metadata and verifier against fixed external pins, reject duplicate JSON keys and require the scoped review result, both independent review dispositions, zero unresolved scoped findings and exact readback count. Hashes authenticate the approved bytes; they are not independent signatures or a substitute for the actual reviews. |
| Live run/attempt/job checks | Lines 220-261 query both exact runs, compare identities, repositories, source, workflow path, event, latest attempt and complete job inventories against the pinned snapshot. Missing pages cannot silently pass: total counts must equal the returned and pinned inventories. All mandatory jobs and steps must be successful; only the two named historical N44 publish jobs may be skipped. |
| All seven original artifacts | Lines 263-282 require the exact seven labels/names, unique positive IDs, expected runs/source, unexpired state and bounded sizes. Each live artifact digest and identity must match its pin, and downloaded outer ZIP bytes must independently match the fixed size and SHA-256. |
| Offline readback and original package | Lines 284-310 run the reviewed verifier under `python -I -S -B`, from a temporary working directory, without `GH_TOKEN` or `GITHUB_TOKEN`. The call supplies the exact candidate, metadata hash and run IDs, then checks the resulting scope, counts, original package and packaged EXE pins. The package is read directly from the verified outer ZIP; no build or repackaging command appears. The verifier and [VERIFY-README.md](VERIFY-README.md) were read to confirm the arguments, 60-group native checks, source/archive identity checks and report limitations. |
| Permissions and secret handling | The job uses `contents: write` and `actions: read` for the publication actions. All three checkout actions use pinned revisions and `persist-credentials: false`. The short-lived GitHub token is confined to the publication step environment; it is removed from the offline verifier environment, is never put in command arguments, and is not copied into provenance or output. All subprocess arguments are passed as arrays; user/data strings are not evaluated by a shell. |
| No overwrite or tag movement | The workflow refuses existing releases twice, including existing drafts. Optional absence is accepted only for a matching REST 404; other API errors fail closed. Existing tags must resolve to the fixed source. It contains no force-push, tag-update, release-delete, asset-delete or upload-clobber operation. A new tag, if necessary, is created at the fixed source only. |
| Draft-first sequence and byte readback | Lines 357-389 create a draft prerelease using the pre-existing verified tag and exact local assets, bind asset IDs/digests, download all assets and compare full bytes. Publication is a PATCH to the exact read-back release ID; it does not re-resolve the mutation target by tag. The corrected final checks detect already-observable asset replacement. |
| Publication claims and release position | The final PATCH keeps `prerelease=true` and `make_latest=false`; the response, public lookup, tag and latest-release status are rechecked. Provenance preserves the unsigned, no-rebuild and no-new-live-host/provider/PostgreSQL acceptance limits. The workflow does not claim whole-project completion. |

## Failure-state and remote atomicity limits

Once a draft exists, the inspected code issues no deletion or cleanup mutation on a pre-publication failure. The concrete failure cases above leave the draft unpublished, and reruns refuse to overwrite it. This is the supported claim; it must not be broadened to “all exceptions leave a draft.”

GitHub's tag lookups, asset metadata checks and publication PATCH are separate remote requests. Another privileged writer can still race a change after the final observation. More basically, a publication PATCH may succeed remotely while the client loses the response or a later metadata request fails. The offline test explicitly reproduces this latter state: the release is public, the workflow has failed, and no success receipt exists. The template does not automatically delete, republish or roll back that state. A failed run after a possible PATCH therefore requires read-only inspection of the actual remote release before any further action. The corrected checks close the concrete P2 gap; they do not manufacture an atomic multi-request transaction or immunity to concurrent authorized writers.

## Reproduction and remaining final-pin gate

From a directory containing the colocated evidence files, use new report paths so the original records are preserved:

```bash
python -I -S -B n47l-publication-review-probe.py --template n47l-publish-template-before-asset-fix.yml --report publication-before-rerun.json --expect vulnerable
python -I -S -B n47l-publication-review-probe.py --template n47l-publish-template.yml --report publication-after-rerun.json --expect fixed
python -I -S -B n47l-publication-guard-probe.py --template n47l-publish-template.yml --report publication-guard-rerun.json
```

No network or actual publication was performed by this reviewer. No repository implementation or executable workflow was modified or pushed by this reviewer. The tests cover the publication tail and unresolved Python guards; no GitHub Actions runner, live GitHub API, actual upload or packaged EXE was executed as part of this publication review.

Before use, bind the real reviewed document commit/tree, PR 28 merge SHA, metadata/summary/verifier hashes, readback count, package/EXE byte sizes and hashes to completed evidence. Confirm the deployed workflow differs from this reviewed corrected template only in those approved pin substitutions and preparation comments. That final factual pin check is separate from this scoped control-flow approval.
