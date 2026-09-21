# N48D — Explicit isolated MCP runtime check

2026-09-21. APPROVED after separate coordinator plan review under the owner's request. Baseline main88c949bad4ea7e15e204008668fde4fdf85e13d2. This complete module depends only on merged Qbrain, not the still-local N48A/B/C integrations. Review is the same assistant in separate engineering passes, not a third party.

## Module and acceptance

Add native mcp-check preview/run with explicit executable and bounded timeout. Preview does not launch or write; run requires its exact digest and freshly rechecks executable identity. Start the approved executable with fixed serve --brain probe --tool-profile memory arguments in a new private temporary home/data/cwd. Provide only a minimal explicit environment, with MCP writing disabled and no inherited provider credentials. Directory/environment isolation is not an OS security sandbox for malicious executables.

Exercise the runtime's explicitly supported MCP2024-11-05 NDJSON lifecycle: initialize, initialized notification, tools/list, ping, close stdin and wait for clean exit. Never tools/call, sampling, auth, roots or real data. Validate response IDs/types/ordering, bounded memory-profile catalog and output; classify failures without exposing arbitrary child text.

Required tests: real Qbrain; deterministic fake peers; partial/invalid/oversized frames; wrong IDs and schemas; startup/exit failure; missing tools; early EOF; stdout/stderr floods; held pipes; stale approval; environment sentinels; cleanup and late errors. Enforce one protocol deadline, byte/message limits and bounded cleanup. Windows uses explicit CreateProcessW, handle allowlist and a newly owned job; Linux a private process group with process identity retained until cleanup. Never terminate unrelated processes or rely on a recycled/reaped PID.

Report actual handshake/catalog/ping/shutdown separately from real agent loading, model utility, write authorization or signed binary authenticity. No logs or raw stream data in the user report. Preview intentionally identifies the approved executable; run output is fixed bounded metadata. Retain existing core/batch/integrity/process tests unchanged and add independent adversarial review/sanitizers. Windows/native and host acceptance cannot be inferred from Linux results. No merge without the relevant executed gates.

## Plan review and boundaries

The principal hazards are blocked or inherited pipes, readers outliving cleanup, SIGPIPE/global signal changes, PID reuse, partial Windows startup, late protocol errors, stale executable approval and unsafe temporary cleanup. Require RAII, explicit inheritance, retained process ownership and a positive clean-shutdown gate. Fixed legacy protocol support is not claimed to be the newest MCP revision. Primary contracts checked: official MCP2024-11-05 lifecycle/transports, Microsoft CreateProcessW/Job Objects and POSIX process/wait semantics.

Only additive CLI/module/tests/CI; no data migration, installer changes, user-brain access, provider call or permission change. Remove the module to roll back. Synchronous OS/file/termination work is not a strict wall-clock guarantee. Last-check races, hostile admins and escaped malicious children are not certified. Refused or incomplete cleanup is reported, never silently called success. Issue40, real client/model/PG/signing and stable-v1 gates remain open. Platform write rejection must not be bypassed. N48A/B/C remain separate unmerged local work.