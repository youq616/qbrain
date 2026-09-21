# Bounded workspace cleanup correction implementation

2026-09-21. This follows WORKSPACE-CLEANUP-REVIEW before acceptance. Process and
workspace cleanup now receive the same2000ms deadline. Only native sharing/lock
errors may cause another removal attempt, and every attempt rechecks the original
root identity. Other failures remain refusals; no permission change or force flag.
The run retains any failed workspace so its destructor does not silently retry.
A fixed optional numeric cleanup error is reported; no filesystem message/path.

Six additional Windows direct checks use directory-list access (not attributes-only
handles) and a non-delete-sharing handle. The transient test starts from an empty
directory to distinguish sharing from not-empty failure. A held handle through a
short explicit deadline must preserve the root and its numeric failure; release
then permits explicit cleanup. The expected native behavior is still pending until
actual execution, not inferred from Linux.172 old process assertions are unchanged.
The new checker adds one malformed cleanup-code variant to the original13 negatives.

The standalone native tests are scheduled before the full original build so a new
boundary failure surfaces earlier. No original build/test step, assertion or
acceptance requirement is skipped. Local Linux172/96 and76 direct tests pass on
these exact product files. Final original CI must run again; previous successful
Linux or Windows partial steps are not substituted for this candidate.
