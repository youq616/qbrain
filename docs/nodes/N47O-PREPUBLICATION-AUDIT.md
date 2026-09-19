# N47O separate pre-publication engineering review

2026-09-19. Reviewer: coordinating ChatGPT, a separate outcome/code/evidence pass
under the owner's instruction. Not a separate subagent or third-party certification.
Verdict: PASS to enable the fixed, reviewed publication; public delivery still pending.

## Actual candidate and evidence

Publisher/test/guide candidate: 4c1362aee78a3f08dec902ac2e0dad77230c6f2e,
tree 1dd106d6cbf83e06a57fa86d89b2b23de21a9b87.
Publisher SHA256 c01890e7b941cb25718e479d8f5ded0576210df709ad3b5fcdd96b713a6f263a.
Successful read-only run: 35410946324, job105810319241. All steps completed/success.
Downloaded artifact10574067584: 2509641 bytes, SHA256
aac533db8bcfeb001599cd93e0d4d5b4af0246dd472bbb049737b184f9afeb04.
The complete 16-member ZIP was checked for CRC; assets, report identities and
SHA256SUMS were read back. The product asset equals the original N44 inner ZIP
byte-for-byte; the START-HERE asset equals the reviewed local/Git source bytes.

The unchanged original verifier rechecked all seven fixed N42/N44 artifacts:
1216 checks, source c26, correct source/review/merge trees, 73 manifest entries,
2117939-byte ZIP and 4077568-byte EXE. Four native validation runs and eleven
artifact IDs were freshly queried, not inferred from past green statuses.
The two authenticated N47N reports cross-compare with 1746 checks each; this
comparison is between their recorded schedules, not a new native product run.
The original checker wording about local schedule is inherited; the new outer
SEARCH-READBACK scope explicitly records what was compared in this delivery.

14 original publisher test methods plus 2 new transport methods pass under both
normal and optimized Python, locally and in read-only CI. All original assertions
remain. Subcases cover draft detection/pagination, wrong tag, failed jobs/source,
missing/different/duplicate/replaced assets, missing digest, interruption, public
state and refusal to become latest. Four separately executed mocked checks for
the additional anonymous-download workflow step cover success, wrong size/hash
and missing publication; these are not real network downloads.

## Code and guide review

Verification runs before publication and read-only mode cannot call publish.
Publication has no PUT/DELETE/clobber fallback. Draft creation's returned ID is
used; by-tag is only used after public transition. Asset IDs are pinned on upload;
metadata, digest and downloaded bytes are verified before/after visibility and
again after downloads. Tag points to tested c26, never workflow or latest-main.
Existing releases/drafts or wrong tags cause refusal, not overwrite. A failure
retains its state; recovery would require an inspected, separately scoped change.

The guide uses the unchanged original PowerShell installer, defaults to no capture,
requires explicit fact/capture choices, refuses overwriting its extraction directory
and verifies both ZIP/EXE hashes. It does not disable antivirus, grant new model
permissions, modify global defaults or bypass host trust. Its commands were reviewed
against the actual installer interface; this review did not execute them on a new
real client. Prior native installer acceptance remains limited to its actual scope.

The publication workflow changes only execution permission/--publish, pins all
reviewed publisher/test/guide hashes, repeats the full verification, and performs
an additional anonymous download of the six public assets with no token supplied.
Its exact repo/branch guard and serialized concurrency remain. No main/PR-triggered
publication is introduced. Product, source tests, installer, schema, canonical
ops ledger and frozen inventory are unchanged.

## Findings and limits

The first read-only run35410588581 failed at Actions artifact download. Its original
log lacks HTTP status. The wrong Accept treatment was corrected and regression
covered; the fresh run passed without changing artifact pins or weakening tests.
See n47o-evidence/INITIAL-FAILURE.md. No historical failure is converted into PASS.

No known blocking issue remains in this fixed delivery scope. Checks observe
states, not an atomic transaction against a concurrently malicious repository
administrator; hash verification is not code signing. The original source/EXE
and old product docs are intentionally preserved, while external guides explain
the new preview. Publication, live-host/model/PG acceptance and full-project
completion are not predeclared. New receipt and public readback are required.
