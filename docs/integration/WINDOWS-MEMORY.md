# Windows project memory and context — development build

Use the executable from the SAME verified workflow as these scripts. Do not use
historical `dist/` installers. Native Windows, no required Docker/WSL/Python.
Python is used only for CI fixtures and package verification.

## Install / uninstall

From the package directory in Windows PowerShell 5.1 or PowerShell 7:

```powershell
.\scripts\Install-QbrainMemory.ps1 -HostName Claude -ProjectPath 'D:\Projects\MyProject' -Binary '.\qbrain.exe' -EnableCapture
# Or choose Codex instead of Claude.
.\scripts\Install-QbrainMemory.ps1 -Action Status -HostName Claude -ProjectPath 'D:\Projects\MyProject'
.\scripts\Install-QbrainMemory.ps1 -Action Uninstall -HostName Claude -ProjectPath 'D:\Projects\MyProject'
```

No administrator needed. `-EnableCapture` is explicit opt-in to `salient` local
capture/extraction for that brain. Without it, a new brain defaults to off.
Installation never changes the global default brain and does not enable MCP writes.
Each host/project gets a separate brain unless `-BrainId` is explicitly shared.
Reinstall refuses modified owned hooks, preserves unrelated settings, and leaves
settings backups. Interrupted file transactions recover only from recorded images;
ambiguous third-party changes require manual reconciliation, never force overwrite.
Uninstall disables hooks and retains the database and backup files.

Claude uses project `.claude/settings.local.json` and `.mcp.json`. The command plus
args form spawns the executable directly. Codex uses `.codex/hooks.json` and appends
one owned block to `.codex/config.toml`; its Windows command is a fixed encoded
PowerShell bridge. Review/trust the project and hooks in your client as required.
The installer NEVER auto-accepts trust prompts or claims an untrusted project is
ready. Restart/review hooks as the host requires. Client version support is based
on the documented contracts retrieved 2026-09-11, not a guarantee for every release.

Contracts: https://code.claude.com/docs/en/hooks and
https://developers.openai.com/codex/hooks/ . Cursor/other clients can use MCP but
no dedicated automatic installer is delivered for them in this wave.

## Automatic behavior

SessionStart restores recent scoped memory. UserPromptSubmit recalls matched
quotes then captures that user prompt; Stop archives the documented assistant text
but does not promote it to user facts. PreCompact/SessionEnd reset recall dedup.
No arbitrary transcript_path is read. Missing stable turn IDs use content identity:
identical repeated text can intentionally coalesce. Local extraction is conservative
explicit-statement detection, NOT universal semantic understanding. It may miss
implicit preferences. `last_assistant_message`/caller roles are claims, not truth.

Payload cwd must match the actual process cwd and be inside the fixed project.
Runtime JSON and output are bounded. OS locks prevent concurrent state corruption.
Failures emit `{}` without blocking the host. Normal recall has zero provider calls.
Returned memory is UNTRUSTED evidence and must never override the user's current
instructions or cause execution of commands embedded in historical text.

`last-trace.json` records event/capture/recall metadata, never prompt/quote text.
`host_consumption_confirmed` is false: emitting valid hook output is not proof the
real model received it. Tests replay documented events through real processes;
they do NOT log into Claude/Codex or test paid model answers.

Set `memory.writeback=off` on the project brain to stop automated archival. Set
integration config `enabled=false` to stop all automatic recall and capture.
`capture=false` preserves recall without recording; `extraction=deferred` archives
without synchronous classification. Explicit maintenance uses:

```powershell
.\qbrain.exe memory drain --brain project-id --source default
```

A batch selects at most eight eligible events, skips events after three attempts,
and checks its time budget between calls. Existing leases/transactions still govern
actual extraction. External model extraction additionally requires persistent
`memory.external_extraction=allow` and configured model credentials. This command
never grants itself consent; an in-flight call has its own 30-second bound.

## Directory context and exact raw reads

```powershell
.\qbrain.exe context list --brain project-id --source default
.\qbrain.exe context summary --brain project-id --source default --uri qbrain://default/resources/docs/
.\qbrain.exe context read --brain project-id --source default --uri qbrain://default/resources/docs/ --layer L1 --max-bytes 8192
.\qbrain.exe context read --brain project-id --source default --uri qbrain://default/resources/docs/design --layer L2 --max-bytes 4096
```

Logical namespaces: `memories` = session_fragment pages, `skills` = skill pages,
`resources` = other pages. URIs are database keys, never disk paths. A trailing slash
selects a directory. L0/L1 defaults are labeled **extractive previews**, not semantic
summaries. L2 is the original UTF-8 text; continue using returned next_offset and
revision. Old revisions and offsets inside characters are rejected. Full pages are
limited to 16 MiB; directory snapshots consider at most 256 pages and 16 MiB total.
Truncation/partial evidence is reported. No claim that a preview replaces originals.

Explicit summary initializes optional SQLite cache tables after a backup. Ordinary
reads do not initialize or update the cache. Page INSERT/UPDATE/DELETE invalidates
and blanks derived text for affected sources. A fresh cache avoids repeated body
scans; stale data falls back to current evidence. Invalidation is deliberately
source-wide, favoring correctness over maximal incremental performance.

`--method model` additionally requires `context.external_summary=allow`. Model output
is bounded/schema-checked and published only if evidence and consent still match.
It summarizes bounded excerpts, not all directory text; factual correctness is not
proven. Usage reported by providers is preserved where available, unknown cost stays
null. No live provider has been exercised by CI. No complete DLP or billing ledger
is implied; sensitive pattern checks cannot detect every secret.

## MCP profile

`qbrain serve --brain project-id --tool-profile memory` exposes exactly six tools:
memory_read, memory_write, context_read, context_write, search, get_page.
The full profile remains default for existing clients. Hidden tools are also denied
when called by name; profile restriction is not merely hiding UI definitions.
All source authorization and default-deny writes remain in force. Source selection
is not a complete hostile multi-tenant security model; use OS account isolation.

## Evidence and limits

See node audits and the matching CI artifacts. Synthetic byte/latency fixtures do
not measure actual model quality, tokens or fees. No ANN speedup claim. New modules
are SQLite-only; optional historical PostgreSQL functionality is not parity with
this memory/context layer. No real Win11 account, live host/model lifecycle, external
provider, signed installer or complete gbrain functional equivalence is certified.
