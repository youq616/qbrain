# N47R — Integrated Windows preview

2026-09-19. Approved for implementation after the separate plan review below.
Base main: c4d0d73931e5bb96f8ae4a6041c3c34477734e56.
Owner requests continued development and separate coordinator outcome self-review.

## Goal

Deliver the accepted N47P installer and N47Q evaluation tools in one usable
Windows download. Stop requiring users to combine an old release with newer
source files. No new runtime behavior, default consent, schema or host adapter.
This is a release-candidate integration, not real-client/model or stable-v1 PASS.

## Acceptance

1. Start from the exact N47O ZIP and verify its digest and original manifest.
   Preserve the c26 EXE/bridge and all retained legacy members. Replace only the
   installer with the exact N47P Windows-tested CRLF bytes. Add pinned N47Q tools
   and current guides. Preserve the original manifest and README as history,
   generate a distinct integration manifest covering every current file, and
   record mixed component source commits explicitly. Do not mislabel as a newly
   compiled EXE or a single-source original N44 package.
2. A deterministic ZIP builder validates fixed file inputs and rejects unsafe,
   duplicate, case-colliding or unexpected archive members; no overwrites of old
   outputs. A verifier compares exact contents and manifests, not self-reported
   PASS counts. Negative tests must reject old/substituted/tampered members and
   inconsistent component metadata, including recomputed manifests.
3. Build the same bundle twice on Linux and Windows and compare bytes. In a new
   Windows extraction, run the actual bundled installer with existing 60 recovery,
   24 snapshot and five unchanged installation/consent/transport suites in both
   PowerShell5.1/7. Run bundled N47Q tasks and file checks for both event formats;
   no synthetic client results promoted to actual model acceptance. Retain raw
   reports, source and bundle hashes. Fresh full native unit gate remains.
4. Separate coordinator review examines actual candidate, negative tests, bundle
   contents and native evidence before enabling publication. Publish only a new
   unsigned, non-latest prerelease with exact tested ZIP and integrity/evidence
   files. Pin asset IDs and compare bytes before/after public visibility and via
   anonymous downloads. Never overwrite old tags/releases or move a tag.
5. Update the current download and completion route only after public byte
   verification. Clearly distinguish installed component readiness from missing
   real-model/host/fees/PG/signing. No fabricated answers or duplicated local tasks.

## Security and rollback

Use synthetic Windows directories, no real user files, accounts, model calls or
persistent settings. Python is build/evaluation tooling, not an application
service dependency. Only new delivery tools/tests/workflow/guides and status
records change; original runtime/installer/tests/ledgers stay fixed. Reverting
source does not remove a public release; any recovery is explicit and inspected.
Plan and outcome review are the same coordinator in separate passes, as currently
authorized by the user, never a claimed separate agent or third-party reviewer.
