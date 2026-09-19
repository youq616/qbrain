# N47O — Reviewed Windows preview delivery

Date: 2026-09-19 (Asia/Seoul). Status: approved for implementation; delivery pending.
Base main: b099c7fb7c8bcd29b5ad40e78a113bbbe82d920a.
Owner requests continued development and a separate coordinator outcome review.
This node closes the gap between accepted N47M/N47N sources and public binaries.

## Fixed scope and acceptance

Publish the original c26ec5e512d9ba960b86c9ced5b9b4976b031f2c N44 inner ZIP,
without rebuilding, repacking or altering EXE/installer bytes, as a new unsigned,
non-latest prerelease. Never modify older tags/releases/assets or the canonical
ops ledger. No production, schema, installer, Hook consent or model changes.

1. Requery all fixed N47N/N42/N44/ledger runs and eleven original artifact IDs.
   Require exact source, attempt, required jobs, successful steps, size and digest.
   Run the inherited seven-artifact verifier, checking source tree, original native
   reports, manifest, ZIP and EXE. Review/merge trees and PR31 must match.
2. Publish only after a read-only CI pass and a separate coordinator review of
   the publisher and negative tests. New tag points at the tested c26 source,
   not the delivery workflow commit or latest main.
3. Create a private draft via REST, retain its returned ID, upload without clobber,
   pin each returned asset ID/size/SHA256, and verify downloaded bytes before and
   after publication. Reject existing drafts/public releases and wrong tags.
   A failure never authorizes deletion, asset replacement or tag movement.
4. Ship an external START-HERE guide, SEARCH-ARGUMENTS guide, PROVENANCE and hashes
   alongside the original ZIP. Explicit read-only installation by default; capture
   and fact flags require deliberate choices. Keep original included documentation
   as historical bytes; external guide identifies this exact new preview.
5. Cover missing/changed/duplicate assets, same-size replacements, wrong tags,
   missing digest, failed/incomplete/wrong-source CI and interrupted publication.
   Public checks must read actual IDs and bytes, not just a successful workflow.
6. Update current download entry and a bounded completion roadmap only after
   verified publication. Separate daily-use v1 from broader parity/research work;
   round estimates are conditional, not elapsed-time or background-work promises.

## Safety, rollback and limits

No user machine or real brain is touched. No new host/provider/PG/signing acceptance.
Existing native Windows evidence remains authoritative for unchanged product bytes.
Publisher uses only this repository, exact branch, contents/actions permissions,
no external secret. Tests simulate GitHub; live mutation is explicit in CI.
A failed pre-publication run leaves a draft for inspected recovery; do not invent
success or auto-retry destructive steps. Rolling back source changes does not
retract a release; any such mutation needs an explicit separately reviewed task.
