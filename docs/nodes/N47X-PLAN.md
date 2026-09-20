# N47X — Deliver the current accepted source as a Windows preview

2026-09-20. Status: approved after the separate plan review.
Base/product source: b810d6898dcbbcd49bdbbed1d8473a3ac1c063e4.
Product tree: 60dd02bc5bfe9c9298f5211d989237ac8262fbf7.
Owner requests continued development and separate coordinator self-review.

## Goal

Close the accumulated source/download gap: one Windows package with freshly built
N47T/U receipt functions, N47V installer, N47W bridge and N47S model tools. Do not
ship the old c26 EXE under new feature labels. Do not add unrelated runtime behavior.
This is an unsigned preview, not stable v1 or real-client/model acceptance.

## Acceptance before publication

1. Check out the exact accepted product source separately from delivery tooling.
   Freshly build its native application and unchanged full60 test groups. Record
   source/tree, build log and EXE hash; do not claim reproducible compiler output.
2. Build a deterministic, allowlisted ZIP twice from that same executable and
   fixed-source files. Manifest records all members and component provenance.
   Installer/bridge CRLF representation is explicit; preserve source contents.
   Reject unsafe/duplicate/unexpected members, stale/substituted binaries, edited
   components and recomputed counterfeit manifests. Never overwrite old outputs.
3. Test files actually extracted from the candidate, not repository stand-ins:
   original receipt75/page71 suites, memory50 tasks, model-tool tests and original
   installer/snapshot/recovery/transport suites in native PS5.1/7. Cover old N47R
   installation -> new path upgrade with existing fact preservation, receipt use/
   listing/revocation, explicit opt-ins then default-off and uninstall retention.
   Keep source-owned tests unmodified and retain raw reports/hash identities.
4. Separate outcome review inspects actual candidate members, source, original
   reports/logs and adverse inputs. First validation workflow is read-only. Do not
   enable publication until native evidence is complete and reviewed. A failed
   test is not a license to relax gates or automatically retry until green.
5. Publish only a new non-latest prerelease after review. Use the exact tested ZIP,
   source/acceptance provenance, hashes, guide and original validation evidence.
   Pin release and asset IDs, read back bytes before/after visibility and anonymously.
   Do not overwrite any old assets/tags or move a tag. Update current download only
   after readback. GitHub repository writes use the currently authorized connector.

## Security, rollback and exclusions

Default capture/write permissions, runtime modules, existing scripts/tests and
canonical inventory stay unchanged. Model tools remain opt-in; no provider key,
real user brain/history or paid call. Tests use disposable Windows data. The code
source is fixed before integration, while delivery source has a separate identity.
Internal construction status is not rewritten after testing; later evidence binds
the same immutable ZIP. Hashes are not code signatures. A new source package can
be reverted, but a published release is not silently deleted or replaced.
Issue40 remains open with its historical cause unknown. N47X integration does not
pass real logged-in-client, model-quality/cost, PG parity, signing or stable-v1 gates.
Review is owner-authorized separate engineering self-review, not another agent.
