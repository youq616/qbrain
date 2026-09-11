# N46A outcome review — maintenance and measurement subset

Auditor: owner-delegated ChatGPT. Verdict: **PASS for the stated integration/measurement subset**.
The integration review was explicitly retrospective for already-written batch/profile code; this record does not re-date it or claim an independent pre-implementation audit. N46 as a whole remains open.

Finite batch and retry limits preserve existing leases/transactions and do not self-grant external consent. The batch's deadline is checked BETWEEN calls. The configured model extraction transport timeout is 60,000 ms, not a guaranteed overall wall-clock limit; an earlier 30-second documentation claim is corrected. Native prompt hooks use local/deferred extraction, not model batches.

The frozen original 108-operation list remains exact, four extensions are checked separately, full profile has 112 tools, and compact list/call enforcement permits six. Six project-local config tests pass. Five parser tests prove that missing/duplicate/failing native evidence is rejected before packaging; nested descriptive assertions are not counted as extra registered groups.

Synthetic Windows benchmark: 96 pages / 860,160 original body bytes; 8,166-byte cached L1 response with truncation explicitly true. Full tool definitions 30,224 bytes versus compact 2,600 bytes. Nine cached process-read samples have 29.4024 ms median on that CI runner. The fixture made zero provider calls. It does not measure token cost, actual answer accuracy, universal latency, or a zero-loss compression ratio.

The verified development ZIP contains the tested EXE, installer/bridge, instructions, licenses and hash manifest. Independent isolated startup without a development DLL PATH passed. The EXE is unsigned and retains upstream internal version metadata, so the source SHA and file hashes identify the preview. A documentation-only repack may correct the timeout sentence without changing executable or script bytes, with original manifest retained.

No ANN, online cost ledger, actual paid-provider evaluation or full gbrain parity has been delivered by this subset. These are not silently marked complete.

## Shared provenance

Tested source: `5ee79dfd5ab2512f024fefc9054bd3da12d64f1f`.
Native run: https://github.com/youq616/qbrain/actions/runs/34616855167
Windows log artifact: 10270422765, SHA-256 `aa73772d02792c2a1b194912b5b92414139f221f9a3d9c82fec2a79b62651624`.
EXE SHA-256: `3bd43e8a099d9b4136aa0b96bd941fed7366a320a09b8bd253a0f272194ecdf8`.
Independent ZIP/manifest verification, registered-group parsing and all gate logs were inspected, not inferred from a green icon alone. Complete results are in `n44-evidence/RESULT.json`. The 44-group status includes a documented skip for actual PG DSN integration.
