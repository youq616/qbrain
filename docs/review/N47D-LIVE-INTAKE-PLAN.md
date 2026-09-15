# N47D live evidence intake and N47E handoff precision

Scope: verify the supplied 18,070-byte live-client archive; keep original bytes
and claims distinct from independent observations. Do not repeat the user's
three sessions or change product source c6c76a2f after its N47E review.

A2's supplied contains_recorded_conflict flag is true because the diagnostic
searched a substring also present in no_live_recorded_conflict. The actual
post-forget CLI JSON and final response show only B; this is not proof of a
remaining product conflict. Preserve the original diagnostic without rewriting it.

Implement a read-only, offline helper that inspects ONLY structured fact_groups
conflict_state values from an already-available Hook envelope or additionalContext.
Do not search quotes/model prose or wrap installer-owned Hook commands. Fail on
unsupported shapes, duplicate JSON keys, malformed UTF-8, unknown states and
oversized inputs. Never echo evidence text or claim client/model consumption.
Empty or truncated context does not certify absence. Reports go to new files.

Plan engineering review (before implementation): accepted with strict provenance,
no product changes, no raw personal transcripts in the repository, explicit
cross-platform negative tests and separate outcome review. Add a v2 local N47E
task with exact typed evidence, no manual seeding, at most three independent
client sessions and a single redacted handoff ZIP. Only logged-in client execution
is delegated; no compiler, GitHub credentials or code changes locally.
