# N47C plan review

Reviewer: ChatGPT, separate owner-authorized engineering self-review.
Verdict: PASS for implementation scope; not external/subagent approval.

The useful next step after fact storage and paired conflict inspection is a
query-bound explicit recall API. Automatic host injection or model extraction
would broaden the change and is intentionally not silently enabled here.

Key safety choices: original object text only, no inferred confidence, and no
single returned matching fact while a supported explicit opponent is active.
Checking opponents only within the query results would be incorrect: the opposite
claim often does not contain the same words. The implementation must load all
same-source outgoing/incoming contradicts edges before publishing that candidate.
Do not call a matching candidate 'verified truth' just because no edge was found.

An exhausted evidence budget must suppress the interrupted candidate, not default
to 'no conflict'. A counts-only omission marker avoids exposing the opponent's
quote without a paired inspection; its semantics are matching-candidate counts,
not global graph cardinality. Same-call read snapshot includes both query match
and opponent status/evidence; the next call must observe deletion/edge creation.
Test that deterministic interleaving with real SQLite connections.

No new writes, schema, provider permissions or automatic call sites. Existing
read/source gates apply with strict action-specific fields; reject history,
event_id and fact_id rather than ignoring them. Preserve old APIs and all gates.
One native group and accurate process exit/counter reports are required, including
negative fixtures and Windows UTF-8 paths. Plan has no P0/P1 blocker after these
constraints. Main risks to recheck at outcome: one-sided recall, incomplete edge
scan, snapshot drift, accidental mutation, and false completeness on truncation.
