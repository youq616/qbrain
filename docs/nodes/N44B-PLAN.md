# N44B — Project-scoped native memory hooks
Status: scoped preview accepted; see N44B-HARD-AUDIT.md. Owner-delegated ChatGPT review; live host/model acceptance remains excluded.

Goal: Connect N43 to documented Claude Code/Codex SessionStart, UserPromptSubmit,
Stop, PreCompact, SessionEnd. C++20 runtime and reversible PowerShell 5.1/7 install.
No transcript_path reads, no models on hooks, no global brain selection change.
Acceptance: bounded nonblocking JSON, canonical project/cwd binding, source-scoped
quote recall and capture, idempotent events, compaction resets dedup, off policy
inert for application tables. Installation preserves unrelated settings, writes
backups/journal, refuses externally edited owned definitions, uninstalls without
deleting memories. Run real-process fixtures and all previous native regressions.
Security: fixed config outside repository; cap all buffers; process lock/atomic
state writes; untrusted quote marker; emission never proves model consumption.
Rollback: remove only owned definitions; retained backups, never erase brain.
Limits: host-attested roles, no general semantic accuracy or PG-memory assertion.
