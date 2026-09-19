# N47S additional review: scenario labels inside evidence metadata

2026-09-19. Reviewed and approved before the correction by the coordinating
ChatGPT in a separate engineering pass under the current owner request.

Final artifact readback of a2fd518c reproduced the recorded engine and scoring
receipts, then a stronger wire-body check failed: although case_id was opaque,
fact evidence session_id still contained names such as changed-conflict-02.
The empty-context unit fixture did not expose this evaluation-label leakage.
Do not declare a2fd final acceptance or quietly narrow the no-label requirement.

Correct only the model-facing projection: parse the known N47Q context envelope
and deterministically pseudonymize session_id metadata with the random plan ID.
Retain original packets exactly in the plan and preserve user quotations,
fact/event/item IDs, predicates, sources and all other evidence fields. Record
the projection in the plan so its approval digest covers the rule. Unknown
context formats or malformed session identifiers must be rejected before calls.
Do not rewrite literal user statements or the original N47Q engine output.

Add nonempty-context tests that assert session label removal, stable pseudonyms,
exact remaining evidence, and no mutation of the source packet. Add the wire
check to the real engine->HTTP integration, where the finding occurred. Re-run
all existing tests and native Windows/Linux workflow on the repaired candidate.

This is a disclosed evaluation metadata projection, not byte-identical full Hook
input to the answering model, and not evidence that a real host uses this form.
The scorer still verifies the original task packets and recorded projected
requests. No runtime/schema/installer/permissions/Release changes or real-model
results. The current known transport and original-scorer constraints remain.
