# N47E follow-up: fresh support for an expired but active assertion

Baseline candidate: aa34e59bc5250b9a63d4af8de4343a1484cc4dd5.
Review date: September 15, 2026. Reviewer: ChatGPT, separate owner-authorized
engineering self-review; not an external or independent-subagent audit.
Disposition: CHANGES_REQUIRED before stage completion or publication.

## Actually reproduced during the outcome pass

With the unchanged candidate rebuilt using Clang17 ASan/UBSan, capture/extract/
promote an expiring whole user quote. Allow its real wall-clock expiry to pass,
then capture/extract the identical quote in a distinct event without expiry.
The new event is valid, but promotion exits 1 with fact_not_found. Ordinary fact
read correctly returns no live claim. Explicitly forgetting the old support and
retrying the new event succeeds. The default lifecycle assertions did not cover
this fresh-event/expired-target transition.

Cause: the grouping query selects the existing active equal-quote fact, but
need() refuses a fact with no currently live support before new support can be
attached. This is a liveness defect, not proof of corrupted data or a privacy leak.
The original candidate's successful CI does not certify the repair.

## Approved narrow repair

Do not change manual create/attach, read validation, retirement or expiry rules.
Keep the exact source/subject/predicate/object/active matching query. When the
selected target has no live support, allow attachment only when EVERY stored
support still validates historically (whole quote, source, hashes, extraction,
role and liveness of the backing page), every support has a strictly positive
expiry already reached, and the stored support count is 1..16. Historical checking
must be used only to establish eligibility inside the promotion write transaction;
never return expired evidence as a live fact. The incoming event remains fully
validated at the current time. Add only its independent current support and advance
the existing revision. Do not rewrite original expiry, restore status, discard
old evidence or create a second fact to evade the support cap.

Retired/superseded equal-quote veto takes precedence. Damaged, deleted, missing,
partially invalid historical support must continue to fail closed. A full support
set remains an explicit skipped_limit, including when its members have expired.
No automatic recovery loop, model inference, schema change or permission change.

## Tests and review gate

Add a real wall-clock scenario covering same-ID renewal, current-only read evidence,
unchanged old expiry, replay idempotence, retired veto, tampering/deleted-page
rejection and the expired full-cap case. Extend real CLI/MCP fixture history with
new events and correct expected exits. Update exact scenario/check/command report
gates, preserving every existing test. Run the unchanged baseline first to prove
the new transition fails, then the repaired unit/process and existing independent
state oracle. Run full Windows and portable workflows on the new commit; retain
all prior CI and failure logs. A separate outcome pass must inspect the repair.

Engineering design review: approved for this scoped fix before implementation.
This document is not a repair outcome PASS. Rollback reverts source only; no
migration or stored-data downgrade. Real authenticated client consumption remains
a separate local acceptance boundary.
