# N47P — Bounded, preflighted installer recovery

2026-09-19. Status: done for scoped source acceptance, not a new public release.
Base:4734fe840081bc2215485e43031fc967b5a93c9d.
Accepted candidate:9feed7c74926d53a7b2a7b21391af02275799f51.
Accepted tree:d396b6170866b83db89e54e26f44685ebcd5c276.
Fixed native push run35415626607; all four required jobs completed successfully.

The original pre-implementation plan is preserved byte-for-byte at
[n47p-evidence/APPROVED-PLAN.md](n47p-evidence/APPROVED-PLAN.md).
Its bounds, recovery, consent, native test and rollback criteria remain unchanged.
The additional input-snapshot fix was separately approved in
[N47P-SNAPSHOT-ADDENDUM.md](N47P-SNAPSHOT-ADDENDUM.md) before its implementation.
Plan review:[N47P-PLAN-AUDIT.md](N47P-PLAN-AUDIT.md).
Outcome and criterion-by-criterion evidence:[N47P-HARD-AUDIT.md](N47P-HARD-AUDIT.md).

The user authorized the coordinator's separate outcome self-review. No separate
subagent or third-party certification is claimed. Journalv1 and2MiB individual
images remain;32MiB is the aggregate journal cap. No C++/schema/permission/default
consent changes, no user-machine task, and no public N47O asset replacement.

The initial58-case harness/root-array corrections remain in INITIAL-REVIEW.md.
Late before-image capture discovered in the subsequent review was repaired and
validated against the exact prior candidate, not covered by its older PASS.
Decoded-text, post-comparison race, non-atomic multi-file and brain-init rollback
limits remain explicit. The scoped source repair does not complete the whole v1
or broad optimization roadmap. Actual merge identity is recorded in PR33.
