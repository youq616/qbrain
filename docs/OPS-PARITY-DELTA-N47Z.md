# N47Z delta — atomic batch management of use receipts

New fact usage-batch-preview/apply reuse memory_read view=usage_batch and
memory_write action=fact_usage_batch. No new MCP tool name or canonical inventory
change.1–32 items across at most8 facts, one authorized source and operation.
Preview is read-only; explicit snapshot-bound apply commits all receipt changes
or rolls them back. Existing single-record semantics and schema remain unchanged.

The module refuses ownership of caller transactions, including implicit pending
statements, before initialization. It is not automatic database repair, a signed
approval, external exactly-once delivery or proof of model consumption.

Fixed7898 Windows/Linux ordinary/-O89 tests, direct18/41 tests and all retained
native/process gates pass. Separate reference-ledger24-round checks match every
summary/page on the downloaded Linux binary. [Audit](nodes/N47Z-HARD-AUDIT.md) and
[usage](integration/USAGE-BATCHES.zh-CN.md) preserve exact identities and limitations.
Public N47X assets remain unchanged; external model/client/PG/signing gates stay open.
