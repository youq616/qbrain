# N47O plan audit

2026-09-19. Reviewer: coordinating ChatGPT in a separate plan review.
Verdict: APPROVED for implementation, under the current owner self-review request.
Not an independent subagent or third-party certification.

The approved c26 binary and installers are kept byte-for-byte, so new native
product rebuilding is unnecessary for this delivery-only node. Source identity
must still be bound to PR31's reviewed and merged tree, not merely main's name.
The existing verifier remains unchanged and runs on fixed native artifacts.

Use the ID returned by draft creation (by-tag endpoints may omit drafts). Pin
asset IDs on upload: size equality alone does not prove identity. Check draft
metadata and downloaded bytes before changing visibility; then repeat public
metadata/tag/digest/bytes checks. Existing release detection must cover drafts
and pagination, treating API errors as errors rather than absence. Use explicit
make_latest=false and prerelease=true. No update/delete/clobber fallback.

A read-only first CI and adversarial unit tests are required before enabling
publication. The guide must not promise that a CLI version string identifies
this preview; the original build's version may be inherited. SHA/source pins
identify it. No automatic install, global configuration changes or capture enable.
No blocking plan issue remains; outcome and actual publication are still pending.
