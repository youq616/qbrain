# N47O final outcome audit — preview delivered

2026-09-19 (Asia/Seoul). **PASS for the approved fixed Windows preview delivery.**
No known unresolved blocking finding remains in this scope. This is not an
absolute absence-of-defects statement, stable-v1 acceptance or full-project completion.
Reviewer: coordinating ChatGPT, in a separate engineering self-review explicitly
requested by the owner. No independent subagent or third-party reviewer ran.

## Exact objects and real results

Product source c26ec5e512d9ba960b86c9ced5b9b4976b031f2c, tree
2beda65c13421a995826c147aad606ea48d7f694; accepted PR31 merge b099c7f.
Reviewed publisher commit 4c1362aee78a3f08dec902ac2e0dad77230c6f2e; publisher
SHA256 c01890e7b941cb25718e479d8f5ded0576210df709ad3b5fcdd96b713a6f263a.
Publication commit 5ec33dd5fefc06a393c0f101139380c0b47ff1f9 changes only the
review record and explicit publication workflow, preserving reviewed tool/test/guide
hashes. Final closing docs and restored read-only workflow are not product build IDs.

| Approved criterion | Actual evidence | Outcome |
| --- | --- | --- |
| Fixed accepted product | Exact candidate/review/merge checkouts and PR31, all four original runs, eleven original artifacts authenticated; unchanged original verifier passes1216 checks. | PASS |
| No rebuilding/repacking | Downloaded product equals original c26 N44 inner ZIP byte-for-byte; manifest73files and EXE hash match. Installer bytes retained in that ZIP. | PASS |
| Review before publishing | First read-only failure retained, corrected read-only run35410946324 succeeds; artifact downloaded/read back before the recorded separate pre-publication review. | PASS |
| Non-destructive publication | New release391866783 and tag windows-preview-c26ec5e5 only; original tags/releases not overwritten; actual draft returned ID used throughout. | PASS |
| Asset identity and availability | All six upload IDs/sizes/digests pinned; downloads match before/after public transition, metadata rechecked after downloads, prerelease/non-latest verified. Additional unauthenticated downloads of all six pass. | PASS |
| Install documentation and permissions | External START-HERE uses original installer interface, verifies ZIP/EXE, refuses existing extraction directory and preserves explicit consent/trust boundaries. Reviewed against original script, not a new host install test. | PASS |
| Status and remaining scope | New download entry, preserved N47N status/README, conditional v1/broad-roadmap estimates added; canonical ledger and runtime remain unchanged. | PASS |

## Verified runs and downloaded evidence

Initial read-only run35410588581 failed at the first artifact download; both
14-method test modes had passed. Exact original HTTP status was suppressed.
Inspection corrected the release-only Accept header incorrectly applied to Actions
ZIP redirects and added safe status diagnostics plus two transport regressions.
No artifact hashes or product assertions were weakened, and no release/tag mutation
occurred in the failed read-only run. INITIAL-FAILURE.md preserves it.

Fixed read-only run35410946324, job105810319241: all steps success. Artifact
10574067584 is2509641bytes, SHA256 aac533db8bcfeb001599cd93e0d4d5b4af0246dd472bbb049737b184f9afeb04.
It was downloaded and all16members, assets, checksums, guide and original ZIP inspected.

Publication run35411136813, job105810867303: all steps completed/success, including
newly pinned script checks, repeated tests, repeated full artifact verification,
publication, anonymous download and upload. Artifact10574137747 is2513491bytes,
SHA256 816a1288b40f66865863d328f501cba57ad969c9cc893371ce8c6432281cf0ed.
It was downloaded and all20members checked for CRC; publication/anonymous receipts,
provenance/delivery source, six asset IDs/hashes/sizes and all five checksum rows
were checked against the actual bytes. Product bytes also equal the prior read-only
and original N44 ZIP. GitHub release and tag were separately reread with the connector.

Release391866783 is public/prerelease; published_at2026-09-19T00:59:05Z. Its six
asset IDs match RELEASE.json. Tag targets tested c26, not delivery/main. The live
API read confirms source and asset hashes; downloads used actual asset bytes, not
merely download counts or metadata. Small original receipt/provenance/checksum bytes
are retained under n47o-evidence, without replacing source IDs by closing commits.

## Test scope and review limits

14 original publisher test methods and 2 transport methods pass normally and with
Python -O locally and in both successful CI runs. Their subcases include wrong tags,
existing drafts/pagination, API errors, failed/missing/duplicate jobs, invalid assets,
missing digest, same-size identity replacement, interrupted upload and wrong public
state. Four mocked anonymous-workflow cases separately pass; the real six public
downloads then passed in CI. The coordinator also separately inspected control flow,
absence of destructive methods and unchanged canonical ledger/installer bytes.

The existing product verifier rechecked1216items across seven N42/N44 artifacts;
the two original authenticated N47N report schedules cross-compare with1746checks
each. This is NOT a fresh native product run, new client lifecycle/model-quality
experiment, or independently authored schedule. Prior native acceptance remains
bound to its actual source/run and includes explicit SKIP-PG. There is no local
execution of the Windows package in this Linux environment.

The public VALIDATION-EVIDENCE.zip includes four verification/metadata records and
nine original native/portable/ledger artifact ZIPs (13members), keeping those logs
available beyond original Actions retention. Source and product archives are not
redundantly embedded; exact source is fixed by tag and product has its own asset.

Hash checking is not signing. Metadata/download checks observe states rather than
an atomic transaction against a concurrently malicious repository administrator.
Errors after public visibility must not be hidden by automatic deletion or overwrite.
The new guide is an external supplement; original included product docs retain their
historical bytes. All new instructions default to no capture and do not alter user
machines. No new PG, live client, model consumption/egress or signing acceptance.

## Completion decision and remaining work

The limited preview-delivery node is done. Closing workflow is restored byte-for-byte
to the previously successful read-only version965aa1d651b10b64a0215b9378e2506ee9eee240.
It cannot publish on normal future runs; the previous explicit publish version stays
in Git history. Closing changes must not alter publisher/test/guide, runtime, original
workflows, canonical ledger or frozen inventory. PR32 records merge/tree readback.
Newly triggered CI is not declared complete in advance.

The project is at public engineering preview, moving to daily-use v1 acceptance.
COMPLETION-ROADMAP.md estimates4–6 further substantive rounds for that scoped v1 and
15–25 for the current broader roadmap inclusive of v1, with explicit assumptions.
They are planning estimates, not elapsed-time promises or a substitute for unfinished
work. Prior host evidence should be reused, not needlessly delegated again. The broad
roadmap remains open; no full gbrain/OpenViking equivalence is claimed.
