# N47D plan review

Reviewer: ChatGPT, separate engineering self-review authorized by the owner.
Verdict: PASS for implementation scope; native outcome remains untested.

The most serious integration risk is independently budgeted ordinary memory
silently reintroducing one side of a dropped conflict. One output composer and
suppression of fact-backed/equal-quote memories prevents that bypass within the
current source/snapshot. Both evidence IDs and exact quote need regression tests.
Retired fact quotes stay suppressed while the fact exists. Ordinary unrelated
memories still work; output need not fit every available candidate.

Use the existing whole-neighborhood validator once for a bounded set of terms,
not eight independent 8MiB calls. Empty prompt terms must not turn into recent
fact enumeration. Only SessionStart intentionally uses recent active facts.
No inferred significance or automatic truth promotion; limits and ordering explicit.
Keep a real read transaction through both lanes and end before writes. Callback
or lock failure must not leave a partly constructed result. Existing off behavior
must remain byte-compatible and require no new schema or backup.

Opt-in is distinct from local capture and from provider extraction permissions.
Hook additionalContext is handed to the already authorized client and may be sent
to its model; do not equate no Qbrain provider call with no external disclosure.
Do not claim actual host/model consumption from replayed events or trace counters.
Status, reinstall and uninstall need native dual-PowerShell checks.

P0/P1 design blockers: none after paired priority, raw-lane suppression and shared
snapshot/budget adjustments. Required outcome checks include both boundary failures
and behavior-preserving previous tests. Same-permission malicious database rewrite
and preexisting client history remain outside the privacy/integrity guarantee.
A separate outcome pass is required; this design verdict cannot certify delivery.

References consulted: https://code.claude.com/docs/en/hooks and
https://www.sqlite.org/isolation.html . Use documented JSON context output, not
workflow decision fields; preserve nonblocking exit semantics.
