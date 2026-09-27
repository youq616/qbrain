# N48N separate plan review

2026-09-27. Reviewer: ChatGPT, owner-requested separate self-review, not a subagent
or third party. Verdict: PASS for implementation against this bounded plan.

Reviewed against main f83d1b13, the N48M load/verify contract, canonical schema and
SQLite's FTS5 and deserialize documentation. Goal addresses an actual untested
layer: SQLite structural integrity is not an external-content index comparison.
The proposed rank=1 check and explicit trigger verification are falsifiable by
independently corrupting index/content synchronization. No mandatory runtime beyond
native C++20/SQLite; Python remains test-only.

P0/P1 before approval: none unresolved. Constraints made explicit in plan:
- Require the existing external pin before inspecting content; do not auto-trust
  a manifest or broaden audit into raw live-file access.
- Never execute the special INSERT against the source backup; private in-memory
  deserialization only, exact accepted DDL and triggers disabled during execution.
- A metadata/count match alone cannot PASS; unknown DDL is UNSUPPORTED. Do not
  normalize quoted literal whitespace in a way that aliases a different content table.
- Do not call this complete application-health or semantic validation. Full FTS
  token consistency is narrower than facts/receipts/embedding/model correctness.
- Preserve actual initial failures and all existing tests/deadlines; qualify native
  Windows before describing Windows support as tested.

P2 boundaries: memory copies/working-set and non-hard-real-time OS calls remain
explicit. This operation detects canonical trigger drift, but does not repair it
or guarantee future writes by external applications. Follow-up changes require
another outcome review; no automatic data writes authorized.

References reviewed: https://www.sqlite.org/fts5.html#the_integrity_check_command
and https://www.sqlite.org/c3ref/deserialize.html .
