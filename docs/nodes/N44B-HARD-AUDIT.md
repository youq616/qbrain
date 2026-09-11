# N44B outcome review — native project memory hooks

Auditor: ChatGPT under the owner's standing delegation, not Claude Code or an independent third party.
Verdict: **PASS for the scoped development-preview plan**, not production/full-project acceptance.
Reviewed against N44B-PLAN.md and the three native compatibility amendments.

| Acceptance | Implementation and evidence |
|---|---|
| Fixed project, bounded, nonblocking Hook | Native C++ hook checks actual cwd/root identities, limits input/output, does not read transcript_path; 69 real-process fixtures pass |
| Recall/capture and resets | SessionStart/user prompt recall, quote provenance, local/deferred extraction, assistant archival without promotion, compaction/end dedup reset |
| Capture opt-in and isolation | Both persistent policy and installation capture switch required; foreign cwd/source and disabled modes tested |
| Reversible project installation | Each PS 5.1/7 passes 69 original installer checks plus 16 consent/path checks, retains unrelated hooks/MCP config and memory |
| Unicode and byte transport | Each shell passes eight checks; actual generated commands are executed by fixtures |
| No global default selection change | `init --no-default` plus local-only config save; six independent process assertions inspect global bytes/other brain |
| Prior behavior | Full production build and all 44 registered groups pass; no golden or assertion removed |

Repairs from failed native runs: true .NET null for atomic File.Replace (34612258237), DB-only settings (34613913091), and logical PowerShell cwd propagation (34615971353). Failures and raw artifacts are retained. The final working-directory fix strengthens compatibility without weakening authorization.

No unaddressed acceptance blocker was found for this scoped preview. Remaining limitations: fail-open integration returns no context when unavailable; source roles are caller assertions; output does not prove a live model consumed it. Default case-insensitive Windows directories were tested, not distinct case-sensitive NTFS installation identities. Native Windows Server CI is not actual Win11/client acceptance. No credentials or real memory were used.

Rollback: uninstall only matching owned definitions, preserve backups and databases; altered owned configuration fails closed. No automatic trust approval or external-model opt-in.

## Shared provenance

Tested source: `5ee79dfd5ab2512f024fefc9054bd3da12d64f1f`.
Native run: https://github.com/youq616/qbrain/actions/runs/34616855167
Windows log artifact: 10270422765, SHA-256 `aa73772d02792c2a1b194912b5b92414139f221f9a3d9c82fec2a79b62651624`.
EXE SHA-256: `3bd43e8a099d9b4136aa0b96bd941fed7366a320a09b8bd253a0f272194ecdf8`.
Independent ZIP/manifest verification, registered-group parsing and all gate logs were inspected, not inferred from a green icon alone. Complete results are in `n44-evidence/RESULT.json`. The 44-group status includes a documented skip for actual PG DSN integration.
