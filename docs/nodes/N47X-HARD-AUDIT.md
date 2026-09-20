# N47X final outcome — current-source integrated Windows preview

2026-09-20. **PASS for the approved native-package and public-delivery scope.**
No known unresolved blocking finding remains within that scope. Stable-v1, real
client/model, PG and signing gates are not passed. Issue40 remains open, cause
unknown. Reviewer: coordinating ChatGPT, in a separate engineering self-review
explicitly authorized by the owner; not a subagent or third-party certification.
This conclusion is not a guarantee of zero defects.

## Exact review objects and ordered approvals

Original plan/review commit: 0a0598e76250b21514a954e7427ffa96387610cb.
Product: b810d6898dcbbcd49bdbbed1d8473a3ac1c063e4,
tree60dd02bc5bfe9c9298f5211d989237ac8262fbf7.
Native delivery: 9831f7ca15d11e868ad1b4fd10deabbb9a3cdca5,
treedbc6b165f6b75e849c5cbec098b2d2c855eab00a.
Read-only publisher review: 944cce17b457ae24c36e87c344f6119efd29387c.
Explicit publication approval: b16d5f799ee37b652c68ab22a047893aa06d45db.
The continuation found PR42 already under development and finished it, rather
than generating another competing package. The unchanged approved plan is in
n47x-evidence/APPROVED-PLAN.md. NATIVE-REVIEW and PUBLICATION-APPROVAL preserve the
review-before-publication sequence. Final merge identity must remain distinct
from the product, native evidence and publisher identities above.

## Approved criteria mapped to actual execution

| Criterion | Evidence and outcome |
| --- | --- |
| Build current accepted product | Fixed b810 checkout freshly compiled with MSVC; original native log has BUILD_OK and all60 registered groups, independently parsed. New EXE is not c26. PASS. |
| Complete and repeatable assembly |27 allowlisted members, exact original source components and declared LF/CRLF representations. Two assemblies from the same new EXE are byte-identical. Original package12 tests passed; verifier reconstructs expected files, not just a self-reported manifest. PASS. |
| Test extracted product and tools |75 receipt checks,71 page checks with333 raw streams, original process regressions,48 packaged model-tool methods under normal/-O, two50-task/520-command event formats and100 loopback HTTP calls. Actual downloaded records were replayed through their original validators/scorer. PASS for synthetic scope. |
| Preserve old data through upgrade |PS5.1/7 each49 checks using old N47R EXE to create a fact, then new package path/EXE/bridge. Retained quote/fact ID, new use/list/revoke behavior, explicit opt-ins, default-off reinstall, uninstall retention and unchanged global default verified. PASS. |
| Retain installer and path gates |Each shell24 snapshot,60 recovery,69 installation,16 consent,8 transport,33 fact-install,33 promotion and84 case-path checks. Source-owned report validators and exact logs checked. PASS. |
| Read-only review precedes publication |Run35501656302 at944c completed with read-only permissions; its downloaded READBACK equals the local reproduction. Only then b16d enables contents:write in one guarded job and --publish; publisher code and native ZIP unchanged. PASS. |
| Publish exact bytes without replacing old release |Run35501790426 created only release392375532 with tag windows-current-preview-b810d689. All5 asset IDs and bytes checked before/after visibility and anonymously. Tag target reread as b810. Downloaded original publication receipts and assets verified locally. PASS. |

The product source is unchanged during this node; added delivery tools/tests and
workflows do not modify C++, installer, bridge, schema, old tests, consent or the
canonical operation inventory. This is integration of already accepted features,
not new semantic algorithms or a claim that more test counts prove model utility.

## Fixed runs and independently inspected files

Native run35479384581, push/attempt1: source105994308433 and native105994308622,
all required steps successful. Original source artifact10595267364 and native
artifact10595995650 were downloaded, SHA/size/CRC/source checked. Canonical trees
reconstruct1188 delivery files and1181 product files;1167 Windows files have exact
LF-to-CRLF conversion, with no other accepted transformation. The separate guide
is CRLF; source-owned application guides remain their fixed Git representation.

Receipt use75/118 and pages71/111 were revalidated. Original process regression
checks: fact34, context65, multiterm112, named arguments60, search arguments226,
Hook facts52, lifecycle batch40, memory44 and MCP17. Fact/multiterm/Hook/batch use
original fixed-source report validators. The legacy context gate preserves only a
summary plus successful CI; this audit does not invent missing raw process files.
Complete task files and the100 actual loopback responses were independently rescored,
not relabelled as real model answers. PostgreSQL explicitly remains SKIP-PG.

Read-only run35501656302/job106054364432, all steps successful. Artifact10602451692:
31428861 bytes, SHA256 b0c8358561bed724d942ed504a71d0a4a90b59e2a2be97016a3316f5a37b8c45.
Local and CI publisher10 methods pass normally and under Python-O. The independent
full file readback also passes in both modes. Twelve extra mutations of the actual
PS5 upgrade report were rejected; the unmodified positive control passes again.
EXTRA-NEGATIVES.json records those tests, not provider or native execution.

Publication run35501790426/job106054723663, all steps successful. Artifact10602522854:
31432683 bytes, SHA256 2177c0a5b55070eb53a521179be8c7f47d550f35dfa7fc1ad7e5f3e860579402.
Its exact product, provenance, checksums, asset pins, public-readback and original
validation archives were inspected; READBACK.json equals the locally reproduced
8053-byte record (SHA256 cb25b4fe6ed3ccbd97996ec9b9d4945259d1303b590ed384680ddbb765f8aa72).
Local tooling did not complete a separate anonymous ZIP download. The anonymous
checks actually ran in the publication job, and their original receipts and bytes
were downloaded and matched locally. No local Windows execution is claimed.

## Published identity and retention

Release392375532, tag windows-current-preview-b810d689, published2026-09-20T09:15:38Z.
The tag points to b810d689. It is an unsigned prerelease, not latest or stable v1.
GitHub immutable-release protection is not enabled; the claim is observed fixed
asset identity and unchanged bytes, not protection against a hostile administrator.

Product ZIP: qbrain-windows-x64-n47x-preview.zip,4327611 bytes,27 members.
SHA256 c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d.
New EXE SHA256838955a0ad88779af08c53396b773d62b327cccd4f216a18379f0a76ffa4c9cf.
Compiler output reproducibility is not claimed; only repeated assembly of this EXE.

Five assets: product ZIP, START-HERE, PROVENANCE, SHA256SUMS and VALIDATION-EVIDENCE.
The evidence ZIP contains both exact original native/source artifact ZIPs and live
validation metadata, so those originals also survive outside short Actions retention.
SUMMARY.json and PUBLICATION-RECEIPT.json pin IDs, sizes and hashes. The package's
construction-time status stays unchanged; external provenance binds later acceptance
to those same product bytes. verification.json precedes publication and correctly
says published:false; publication.json is the subsequent actual state transition.

## Review findings, boundaries and final decision

The earlier continuation corrected unchanged process-harness Git provenance by
running those harnesses in the fixed checkout while passing the extracted EXE;
it did not add fake .git metadata to the product. Local exploratory checks initially
assumed LF for the separate guide and uniform legacy report fields; these assumptions
were corrected against actual exact bytes and source-owned formats. Neither the
product ZIP nor any original test expectation was weakened to produce acceptance.
No new blocking product finding was established during this delivery review.

The publisher defaults to read-only, pins exact run/source/job/asset identities,
refuses an existing release/draft or inconsistent tag, and never deletes or overwrites
old assets. Errors leave evidence rather than silently retry. Publication uses only
the explicitly authorized repository workflow token, not personal or model credentials.

This release closes the accumulated source/download gap through N47W. Default
capture/write permission remains unchanged, and use receipts still mean caller
attestation rather than observed consumption. Issue40, real signed-in-client use,
actual model quality/cost, PostgreSQL parity, signing and stable-v1 acceptance remain
uncompleted. Historical internal version2.0.0 is not stable-v1 certification.

Closing changes must be documentation/history and derived receipts only. Compare
against b16d before merge, preserve all tested product and delivery code, and reread
actual main/merge tree afterwards. Do not predeclare any newly triggered CI success.
