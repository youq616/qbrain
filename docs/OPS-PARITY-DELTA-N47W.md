# N47W delta — process bridge diagnostics

N47W modifies only scripts/Invoke-QbrainJson.ps1 among inherited production files.
Optional success metadata and failure Exception.Data identify process-bridge phases
without raw content. Input waiting now consumes the same remaining elapsed budget
as process and output waits; the original default/range/messages are retained.

No MCP operation, persistent schema, installer or Hook definition, source permission,
consent, model request or canonical inventory change. No automatic error logging or
process-tree kill. Issue40 stays open: its old timeout was not reproduced or fixed
by these deliberately induced native transport failures.

Both native shells passed29 checks/6 observations and the original installation
gates; the unchanged full60 native suite passed. See [review](nodes/N47W-HARD-AUDIT.md)
and [usage/limits](integration/TRANSPORT-DIAGNOSTICS.zh-CN.md). Source acceptance is
not a replacement of the N47R public package or a stable-v1 result.
