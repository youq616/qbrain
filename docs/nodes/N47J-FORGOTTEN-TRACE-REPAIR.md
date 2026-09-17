# N47J outcome finding: retain forgotten-replay diagnostics

Candidate: d29f5efad8b928fa0f1947bd0f4fc5befc659b23.
The original native workflows passed, but a separate real-CLI experiment on the
unchanged candidate found a P2 diagnostic correctness defect on both host formats.
After an accepted user event is captured/extracted/promoted, explicitly forgetting
that event and replaying the same event returns capture status `forgotten`.
Extraction correctly rejects the tombstone; the memory remains absent. However,
`hook_trace_record` omitted this legitimate capture state from its allowlist,
so projection threw and both old trace files remained at processed/complete with
capture_status=archived. This was not a memory resurrection or permission defect.

## Narrow correction approved before implementation

Allow the exact enum `forgotten` for capture_status only. Extraction still throws
for a forgotten event and does not return that state. Do not accept arbitrary
strings, copy exception text, modify the memory tombstone, widen collection
permissions or claim a completed extraction. On local replay record failed/extract
with capture_status=forgotten; in deferred mode record processed/complete with
capture_status=forgotten, without implying the event was re-created.

Add a named metadata scenario for these two cases and keep extraction's allowlist
strict. Extend the true CLI/Hook suite for both host formats with a fresh synthetic
event, a real memory read and forget, replay, absence check and deferred replay.
Require new scenario/command schedules in the source-bound report validators and
negative report tests. Check last-trace equals the event record after replay,
absence of original content, and unchanged no-resurrection behavior. Preserve the
original reproduction and all previous assertions; the earlier green artifact is
not acceptance of this repair.

Engineering plan review: accepted for this bounded enum-and-regression change.
Run fresh Windows/portable/sanitizer gates on the changed source before outcome
closure or release. No schema, runtime state, authorization or new host acceptance.
Review is owner-authorized separate engineering self-review, not third-party.
