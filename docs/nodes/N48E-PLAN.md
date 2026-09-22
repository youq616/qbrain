# N48E — Complete OpenCode project configuration lifecycle

2026-09-22. Status: done for approved source integration and pinned V1 host scope.
Base main:ce2e26201fcdf977a507f895c081ab09f83359b8.
Original approved plan and embedded separate plan review:e679a0af23c63e47879c48b383500c7731e6a229.
Accepted integrated source:206d04eb4a04588007224cc98d56909b0b52a965.
Accepted tree:3de27b2ef0b5f9b408e6e31d861f7507de683fcc.
Original product/host-tested source:e419acf60375e1a7a0794375c713f759b776aa0b.

[Original plan](n48e-evidence/APPROVED-PLAN.md) remains unchanged. The separate
engineering outcome review is [N48E-HARD-AUDIT.md](N48E-HARD-AUDIT.md). The current
user expressly requests coordinator self-review; no third-party/subagent review
is claimed. Final merge identity is in PR46, not substituted for native evidence.

The complete project lifecycle integrates prior A/B/C local work: preview, install,
status, read-only audit, uninstall, recovery and external-edit reconciliation.
Pinned OpenCode1.18.31 loads/connects on both platforms. V2 input compatibility
omits the stage timeout; native V2, model consumption, PG and signing stay untested.
No public package/tag is replaced. The prior blocked archive write and local-only
handoff remain historical; their completion is not claimed before actual merge.
