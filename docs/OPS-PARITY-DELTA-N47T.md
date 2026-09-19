# N47T delta — explicit fact-use receipts

2026-09-19. New source capability within existing memory_read/memory_write;
no new MCP tool name, operation-count increase, Hook default or authorization.
The canonical ledger/frozen inventory remain unchanged.

`fact report-use` records an authorized caller's explicit current-revision
attestation; `fact revoke-use` retains an irreversible receipt tombstone;
`fact usage --id` gives bounded current/historical/withdrawn counts. No automatic
recording by Hook/read, ranking change, decay, fact truth or host-consumption
proof. SQLite-only optional module with pre-module backup and parent-fact delete
cascade; not a global version migration and not PG parity.

Fixed6e6ca6e8 native/portable75checks/118calls and retained process gates pass;
fresh native60groups and portable4focused groups pass. Additional separate
Linux12-case review and14negative report inputs were executed. See
[N47T audit](nodes/N47T-HARD-AUDIT.md) and
[usage/limits](integration/FACT-USAGE.zh-CN.md).

This is source acceptance, not a new public package. The N47R download stays
unchanged and lacks these new commands. Actual model/client and v1 gates remain.
