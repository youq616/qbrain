# N47L fixed-draft recovery review

Reviewer: separate actual ChatGPT subagent `/root/recall_storage_review`, under the owner's engineering review authorization.

Plan gate: **PASS_FOR_IMPLEMENTATION**, issued before the implementation agent wrote the recovery workflow. Final outcome: **PASS_RECOVERY_CONTROL_SCOPED** for workflow SHA-256 `d81f84d3dd0b2f83b05ad6812fdca4f7105db0ee36a85624041b68add42f60f3`. No unresolved P0/P1/P2 finding remains in this bounded recovery implementation scope. No recovery publication has been performed by this reviewer. This is a new recovery record. The original frozen publication-control and final-pin reviews are historical records and are not rewritten to imply successful live publication.

## Observed initial failure

I independently queried the GitHub run, latest-attempt job and release-by-ID endpoints, and read the actual job log. [N47L-RECOVERY-INITIAL-FAILURE.json](N47L-RECOVERY-INITIAL-FAILURE.json) preserves the normalized observations and relevant log excerpt.

[Initial publication run 35233247840](https://github.com/youq616/qbrain/actions/runs/35233247840), attempt 1, at commit `2f254681c31fd493fa9cb5ab14ae089608f8a4ad` actually **failed**. The log records the original artifact verifier's 1094-check PASS, followed by an exception at `draft=api('releases/tags/'+tag)`. That statement precedes the publication PATCH. The live release-by-ID query confirms draft **390787606** exists, remains unpublished and contains the three uploaded assets below.

The failed draft lookup uses a published-release route. GitHub describes the tag endpoint as retrieving a published release; the recovery must use the known release ID while it remains a draft. This is a discovered endpoint-contract error, not a reason to weaken credential checks or assume a transient authorization failure. [GitHub release-by-tag documentation](https://docs.github.com/en/rest/releases/releases#get-a-release-by-tag-name).

The asset-by-ID route supports binary content through `Accept: application/octet-stream`, including direct 200 responses and redirects. [GitHub release-asset documentation](https://docs.github.com/en/rest/releases/assets#get-a-release-asset).

| Existing asset | Fixed ID | Bytes | SHA-256 |
| --- | --- | --- | --- |
| `qbrain-windows-x64-multiterm.zip` | `570420529` | `2114341` | `ed44a43d79e1e76efa768e74872223cd5d867dfb92881fe67aab129789cd4408` |
| `PROVENANCE.json` | `570420531` | `2049` | `6cc243b432dbb444f83f9983f4294d0a4c516edc2ad0180b9a2940cc810cd59a` |
| `SHA256SUMS.txt` | `570420528` | `181` | `5cd993f0e3a1fe73cfb818706f27e353902738ceabb5e01482b120489c0d715b` |

All three live API rows have `state=uploaded` and matching digests. The release has the fixed `multiterm-preview-17e9a435` tag, source target `17e9a435f94e45b3ca22d3da062ba4683c135c4b`, expected title, `draft=true`, `prerelease=true` and `published_at=null`.

## Independently approved recovery plan

The implementation agent received plan approval only after these observations, and only for this bounded recovery:

1. Preserve the fixed tested source/tree, reviewed documentation/merge, both original CI runs, complete live job checks, all seven original artifact pins and the 1094-check offline verifier gate.
2. Address exactly draft `390787606` by release ID. Require its full expected identity and the fixed three asset IDs, sizes and digests. Reject an already-public, missing or changed release. Require the existing tag to point to the fixed source; do not create or move it.
3. Download the three existing assets by their fixed asset IDs using the binary media type, verify their byte counts/digests and compare the product to the original verified CI inner ZIP.
4. Preserve the original `PROVENANCE.json` and `SHA256SUMS.txt` bytes. Validate their meaning against the original delivery run/commit and fixed source/review/CI/package evidence. The old delivery run identifies the process that generated and uploaded these bytes; it must not be relabeled as a successful publication run.
5. Make the sole remote mutation a PATCH publishing this exact verified draft ID. Do not create, delete, replace or upload any tag, release or asset. Recheck public release/tag/asset identity after publication.
6. Write a new recovery receipt that separately records the recovery run/attempt/commit, retains the original provenance identity and explicitly states that the initial run failed. Pre-PATCH failures leave the existing draft unmodified. Preserve the previously documented remote-PATCH non-atomicity limit.

Required independent outcome checks include preservation of the original gates and fixed bytes; an actual-code offline control with draft-by-tag unavailable; same-size/new-ID/digest/extra/missing asset cases; wrong/missing/already-public draft and changed tag; metadata/body corruption; proof that no forbidden create/upload/delete calls occur; and failure before the only allowed PATCH.

## Implementation and independent outcome review

Reviewed recovery: [n47l-publish-recovery.yml](n47l-publish-recovery.yml), 431 lines, SHA-256 **`d81f84d3dd0b2f83b05ad6812fdca4f7105db0ee36a85624041b68add42f60f3`**. The initial endpoint-contract P2 is addressed by this fixed-draft recovery; the old workflow and its reviews remain frozen historical evidence.

The original publication simulation had allowed draft lookup through the by-tag route. That transport assumption did not model GitHub's published-only contract and missed the real failure. The recovery simulation below explicitly returns 404 for every draft-by-tag request. This record does not retroactively change the earlier simulation results or claim that the first publication run succeeded.

I compared the actual code bytes with the frozen final workflow, SHA-256 `389b6f38cf695e2f1ebfe149761e45ccd5b8dac35142f97e8ff1650991fe7a3a`. The first pin guard is unchanged. The source/review/merge and committed-summary/evidence gate segment is unchanged. The complete live CI run/job/step, seven-artifact and 1094-verifier segment is also byte-identical. These are preservation checks, not claims of new native test execution by this reviewer.

The new fixed fields match the independently observed draft ID, initial failed run/attempt/commit and three asset pins. The code requires the existing exact source tag and checks the same release by ID before CI readback, before asset download, and immediately before publication. It also rechecks that the initial run actually failed at the pinned commit.

Binary downloads use the fixed asset IDs and the explicit octet-stream header. Each downloaded body must match its original byte count and digest; the product must also equal the original verified CI inner ZIP. The parsed original provenance must equal the full expected source/review/CI/package and initial-run object, while its exact uploaded hash remains separately fixed. The checksum text must bind the original product and original provenance bytes. The code never writes, regenerates, replaces or uploads those remote release assets.

The only Release/tag/product-asset mutation is the PATCH to **390787606**. It preserves prerelease status and does not make the release latest. All draft operations use the release ID; by-tag lookup is used only after publication succeeds. Exact release ID, source, tag, title, state and the full fixed asset ID/size/digest inventory are checked on the mutation response and subsequent public lookups. The inherited Actions evidence-artifact upload remains an audit-output operation; it is not a Release asset replacement.

The recovery receipt keeps `delivery_run` and `delivery_commit` from the original provenance, adds explicit `initial_delivery_*` fields with conclusion `failure`, and records separate `recovery_run`, `recovery_run_attempt` and `recovery_commit`. It records `original_assets_replaced=false`. The three original assets and before/after release metadata are retained in the workflow evidence for post-run readback.

## Actual offline verification

The independent [n47l-recovery-review-probe.py](n47l-recovery-review-probe.py) executed the workflow's real helper definitions, fixed-draft preflight and entire recovery tail. Only the subprocess transport was doubled; the actual API wrapper, fixed-ID selection, release/asset checks, byte reads, provenance comparison and receipt construction ran unchanged. The transport rejects any unplanned external command, Release/tag/product-asset mutation or unauthorized endpoint. Draft-by-tag always returns the documented published-only absence behavior.

The final stable run exited **0** with **22 cases** and the exact frozen recovery hash. [N47L-RECOVERY-OFFLINE-REVIEW-FINAL.json](N47L-RECOVERY-OFFLINE-REVIEW-FINAL.json) preserves every result:

- **One positive control**: a still-draft release inaccessible by tag is recovered through its fixed release ID and three fixed asset IDs; the only mutation is one PATCH to 390787606. The receipt retains original failed-run provenance and separately names the simulated recovery run/commit.
- **Twenty pre-publication negative cases**: missing/already-public/wrong-ID/wrong-source/wrong-tag draft; a tag changed after download; new/wrong/missing/duplicate/extra asset identities or metadata; corrupt product/provenance/checksum bytes; JSON metadata returned instead of binary content; asset replacement after readback; wrong initial commit or a falsely successful initial run; and a failed final API read. Every case stops with **zero publication PATCHes**.
- **One remote-commit/connection-failure case**: the fixed PATCH commits remotely and its connection fails. Local execution fails and emits no success receipt while the simulated release is already public. This retains the earlier non-atomicity limitation instead of pretending recovery makes the operation transactional.

All 22 cases made **zero draft-by-tag requests**. No network or actual publication occurred in the simulation. The source/CI/verifier gates were not simulated as fresh passing CI; their byte preservation was checked separately.

The positive fixture uses the original authenticated CI inner ZIP. The provenance and checksum fixture bytes were reconstructed from the frozen original code and actual initial run identity, then individually verified to match the live draft's recorded size and SHA-256. They are explicitly described as reconstructed fixtures, not as downloaded draft bytes. The real recovery workflow performs fresh binary downloads by asset ID and verifies them independently.

To repeat the offline checks, provide a fixture directory containing the exact three files with the fixed hashes above, the committed evidence directory and a new report path:

```bash
python -I -S -B n47l-recovery-review-probe.py --workflow n47l-publish-recovery.yml --original n47l-publish-final.yml --fixture <exact-original-three-assets> --evidence <repo>/docs/nodes/n47l-evidence --report recovery-review-rerun.json
```

## Disposition and limits

**PASS_RECOVERY_CONTROL_SCOPED** approves only this exact one-draft recovery implementation and its fixed bindings. The initial run remains an actual failure, and this review does not mark either the original or recovery run successful. The unchanged runtime gates and real release-ID/asset-ID downloads must still complete before the only permitted PATCH.

The earlier remote non-atomicity limitation remains. A failure after a potentially successful PATCH requires read-only inspection of the actual release; rerunning against an already-public release is refused. No source/product runtime, local user installation or new provider/PostgreSQL acceptance is part of this recovery.

This reviewer performed only read-only GitHub/docs queries and local scratch review/probe work. No recovery workflow, branch, tag, release or asset was pushed, created, deleted or published by this reviewer.
