# N47V — Refuse ambiguous Windows installation paths

Status: done for scoped source acceptance, with a tracked non-blocking observation.
Recorded: 2026-09-19 UTC. This is 2026-09-20 in Asia/Seoul at final review time.
Base main: 98b45d264696a23552ca14d12218555c57087528.
Original pre-implementation plan: 2e8ccaac0ceb2127e752de4c222f5fb10c7b1df7.
Product and original regression source: 192cdec2c3a39b6f35e7f6521d779425e61fee17.
Product/test tree: 92ff4e582c49d92839614f3ef903fee6e9effaf0.
Supplemental review source: b28a6378b7e5ceb3b4ea785317905a891d363da0.
Supplemental tree: c1c59d1a1c31b6402136d6ed410bc70e8e02764b.

The [original approved plan](n47v-evidence/APPROVED-PLAN.md) is preserved unchanged.
[N47V-HARD-AUDIT.md](N47V-HARD-AUDIT.md) maps it to actual code and native evidence.
The supplementary source adds tests/workflow/review plan only; installer bytes
remain fixed. Final merge identity is recorded in PR39, not substituted for a
build identity. No publication is performed in this stage.

This refuses unsupported or unverifiable case-sensitive paths; it is not full
case-sensitive-project support and does not migrate IDs or change filesystem flags.
The owner-authorized coordinator conducted separate engineering review passes,
not a subagent or third party. Issue40 retains the unresolved cause of one old
Codex Hook startup timeout; an identical job retry passed without weakened limits.
The limited path-guard approval does not close that issue or stable-v1 acceptance.
