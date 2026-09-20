# N47X publication approval after native and read-only review

2026-09-20. Owner-authorized coordinator separate outcome review. APPROVED for
one new unsigned, non-latest prerelease of the exact accepted ZIP, not stable v1.

Native package/source review is in NATIVE-REVIEW.md. The same verifier and publisher
now passed live read-only workflow35501656302 at944cce17b457ae24c36e87c344f6119efd29387c,
job106054364432. Every step succeeded; no publication call was made. Original output
artifact10602451692 was downloaded:31428861 bytes, SHA256
b0c8358561bed724d942ed504a71d0a4a90b59e2a2be97016a3316f5a37b8c45.
Its full READBACK.json equals the independently reproduced local output exactly.
All five proposed assets match their recorded bytes/hashes; the evidence ZIP holds
both exact original source/native artifacts and authenticated validation metadata.
The product ZIP remains c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d.

Publisher tests10 methods passed normal/-O locally and in CI. Twelve additional
mutations of the actual PS5 upgrade report (wrong shell/type, failure, substituted
binary/ZIP, missing/duplicate/false check, false client claim, unexpected field,
wrong script and altered log) all reject; unchanged control passes again.
These negative checks are evidence validation, not new Windows execution.

Reviewed state machine refuses an existing release/draft, failed listing, wrong tag,
missing/replaced/incorrect assets and modified local files. It pins all uploaded
IDs, rechecks their IDs and bytes before and after making the draft public, and
performs unauthenticated downloads. It never overwrites/deletes old releases or
moves tags. API errors leave evidence, not an automatic retry/cleanup sequence.

Only this workflow job gains contents:write; actions stays read. The same reviewed
Python blobs, their SHA gates, original native tests and product bundle are
unchanged. Add --publish only after this approval. Repository workflow changes
are committed using the authorized GitHub connector; the workflow's own token
performs its explicitly authorized release operation. No user credential is read.

Do not declare publication complete until actual release/asset readback succeeds.
If it fails, preserve the exact draft/public state without inventing a success.
Issue40 and real client/model/fee/PG/signing gates remain open. This review is the
same coordinator in a separate pass, not a subagent or third-party certification.
