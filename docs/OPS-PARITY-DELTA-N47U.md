# N47U delta — inspect existing use receipts

Accepted source b7f93bdce18cfc28e48d4cc7d1ef06a32d901831.
`fact usage-list` and memory_read view=usage_receipts add metadata-only discovery
of current/historical/withdrawn usage IDs, stable ordering and bounded pages.
Continuation needs after_id plus a matching source/fact/filter/data fingerprint;
state changes require restart. This is not authorization or a retained transaction.

No new tool name, stored schema, write permission, automatic usage, Hook default,
ranking or decay. N47T receipt writes and FactStore remain unchanged. Canonical
ledger and frozen inventory remain intact; this delta does not replace them.

Both platforms passed71 page checks and75 inherited usage checks; Windows full60
and Linux4 focused groups passed. [Outcome review](nodes/N47U-HARD-AUDIT.md) records
raw artifacts and independent boundary probes. [Usage](integration/FACT-USAGE-AUDIT.zh-CN.md)
explains paging/restart and the source-only release boundary. Real model/client/PG
acceptance is still uncompleted, and existing public assets remain unchanged.
