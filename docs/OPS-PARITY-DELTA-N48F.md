# N48F delta — caller-normalized offline token-cost reporting

Native cost report prices disjoint usage buckets with explicit rate cards and
checked fixed-point arithmetic, including reported failures/retries. It does not
add MCP tools, persistent telemetry, provider calls, prices, schema or permissions.
Canonical operation inventory and old command semantics remain unchanged.

Fixed5990 source passes Windows/Linux103 direct and149 process checks per Python
mode, plus original runtime/lifecycle gates. A separate398-call rational reference
and sanitizer review pass. See [audit](nodes/N48F-HARD-AUDIT.md) and
[usage](integration/TOKEN-COST.zh-CN.md). This closes the offline calculation layer,
not authenticated end-to-end billing, complete automatic capture or demonstrated
model savings. Existing public N47X assets and external acceptance gates remain.
