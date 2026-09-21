# Final-candidate Windows workspace cleanup finding and correction plan

2026-09-21. Same coordinator, separately reviewing the actual00f native outcome.
Run35592198963 Windows106308951071 passed the original build/full60 and standalone73,
then failed the held-pipe fixture after127 process checks. Original artifact10635417350
is16674312 bytes/SHA2563abbde3f43d9a453230cf220feecf09a4eaa84aa5f19022e12006591f66048e6.
The actual report has protocol phase shutdown, direct exit0, process cleanup true,
workspace cleanup false and result FAILED/code cleanup_incomplete. It correctly
refused success. Do not call this a completed Windows acceptance or infer an exact
filesystem error code that the old report did not retain.

APPROVED correction before implementation: share one2000ms cleanup-wait deadline
between process and workspace cleanup. On Windows only, retry removal only for
explicit sharing/lock violations, with identity rechecks and the same fixed deadline;
never change attributes, force access, retry arbitrary errors or delete a replaced
root. Failed cleanup retains the workspace, including on destructor exit. Add a
fixed optional numeric workspace cleanup error observation, never raw path/error
text. This is bounded cleanup waiting, not repeating the protocol/model call.

Add separate native tests with a deliberately held directory handle that refuses
delete sharing: observe the actual OS refusal, release it and verify bounded cleanup;
keep it held through a short test deadline to prove failure/retention, then explicitly
release and clean. Retain every172 process assertion and existing original gate.
No increase to protocol timeout or total cleanup waiting budget. The old observed
failure remains evidence; a transient-lock explanation is an investigated mechanism,
not a retrospectively observed error code. Re-run the changed final native source.
