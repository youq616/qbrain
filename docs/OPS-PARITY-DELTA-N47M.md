# N47M ops delta — scoped source acceptance

Accepted 2026-09-18; final review: [N47M-FINAL-AUDIT.md](nodes/N47M-FINAL-AUDIT.md).
Existing operations only: memory_read, memory_write, local memory drain,
context_read and context_write. No new tool, migration, external permission,
Hook default, semantic capability or ops-count increase.

The memory/context CLI now reads named values and flags only from validated
option positions. Option-shaped query/source/brain contents cannot override
actual arguments or grant manual capture consent. Existing operation/source
permission and provider-consent checks remain authoritative. Explicit empty
values, default values, existing errors and brain precedence are preserved.

Full N42/N44 native gates on 15f6f396, 1,177 checks over seven fixed artifacts,
67 original process checks with baseline comparisons and 937 separately authored
black-box self-review checks passed. The latter two were executed on Linux;
N47M's original Windows process run independently records 60 checks/113 commands.
See the final audit for source equivalence and distinct executable identities.

Reviewer: coordinating ChatGPT in a separate engineering self-review explicitly
authorized by the owner on September 18. Not a separate agent or third party.
No known unresolved blocking issue remains in this node's reviewed scope.
No new public release is created; the N47L download does not contain this fix.
Search grammar and real PostgreSQL acceptance remain outside this node.
