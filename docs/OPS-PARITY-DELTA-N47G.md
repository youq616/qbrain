# N47G capability delta

Tested source b1292b54543b9f54cd5e2b71f4ae4bf5f6247385, tree
572dce7081140b7869821e9e2f98b7f1429d6328. Native development35093371931 and
N4235093372100 passed; see N47G-HARD-AUDIT.md for separate outcome review.

Added fact batch-preview / fact batch-apply and FactStore::lifecycle_batch.
Existing memory_read(view=lifecycle_batch) previews without writes or reservation;
existing memory_write(action=fact_lifecycle_batch) applies archive/restore to1..32
explicit same-source selections atomically. Current revisions and live evidence
are required even for no-ops. Duplicate IDs/raw JSON keys and irrelevant arguments
are rejected. Complete receipts contain metadata, not copied user quotes.

This is not a loop of independently committed operations. One failing member or
SQL/commit error rejects the entire policy/revision batch. Preparation may leave
an N47F backup/empty module; that documented boundary remains. Archive preserves
valid direct counterclaims; restore cannot revive retired or forgotten facts.

No new schema, MCP tool name, consent/default setting, model call, semantic merge,
auto-aging, usage count or scheduled job. The previously advertised lifecycle
stale_after_days MCP field is now correctly routed with a real positive regression.
55 exact native groups, new15/259 unit and40/54 process evidence, original gates,
ASan+UBSan, and additional5/67 commit-failure probes passed within their stated scope.
