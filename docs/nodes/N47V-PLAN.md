# N47V — Refuse ambiguous case-sensitive Windows installation paths

2026-09-19. Status: approved after separate plan review below.
Base main98b45d264696a23552ca14d12218555c57087528. Owner requests continued
development and a separate coordinator self-review. This addresses the explicit
Issue2 N44 case-sensitive NTFS identity gap, not a new usage-report feature.

## Problem and bounded decision

The existing project integration ID lowercases the full project path. Windows
NTFS can contain distinct Projects/A and Projects/a when their parent is marked
case-sensitive. Existing Status can read the other project's owner record; a
new spelling-dependent ID would also conflict with old installations and other
runtime components that assume insensitive paths. Do not silently migrate IDs.

Keep ordinary case-insensitive installation identities/behavior unchanged.
Reject Install, Uninstall and Status if ANY existing directory component of a
project, managed config/temporary/backup path, binary or owned data path is
case-sensitive or its sensitivity cannot be verified. This is fail-closed
unsupported-path protection, NOT full case-sensitive-project support.

## Acceptance

1. Read directory attributes through a native handle, never parse localized
   fsutil output for the product. Open for metadata only, share read/write/delete,
   use backup semantics and open-reparse-point. Check handle attributes/type and
   case flag (FileCaseSensitiveInfo). Dispose every handle on success/error.
2. Extend the existing Safe path checks, including ancestors and the existing
   repeated checks before recovery/writes. Do not cache directory sensitivity
   across checks, enable/disable filesystem flags, create probe files, use admin
   elevation, initialize a brain or change installation IDs as a fallback.
   Inability to open/query metadata fails closed, not assumed insensitive.
3. Add actual NTFS Windows tests under PowerShell5.1/7: create distinct A/a
   projects, demonstrate the old lowercased identity/status collision, then
   require candidate rejection and unchanged project/owned/journal/brain bytes.
   Also cover a sensitive project itself, sensitive hidden config directory,
   binary parent, owned-data ancestor and pending recovery. Check both hosts and
   all actions. Ordinary paths remain usable with unchanged legacy IDs, defaults,
   Unicode/spaces/quotes and existing installation/upgrade/uninstall behavior.
4. Keep original24 snapshot and60 recovery cases and all five native installation
   suites unchanged. Run them against the candidate on both shells; keep the
   full original native60-group gate. Record exact source/script/EXE and every
   native case; unsupported test-host NTFS capability is a failure/pending gate,
   never a skipped PASS. Use only disposable CI directories; elevation is only
   for creating the test NTFS flag, not required for product queries.
5. Separate outcome review: inspect code/cleanup, actual raw reports, controls and
   fixed source; correct blocking findings and revalidate. Update status/roadmap
   only with real results, keep unsupported-path versus full-support distinction.

## Limits and rollback

Same coordinator performs owner-authorized separate plan/outcome self-review,
not another agent or third party. Add-Type uses the native PowerShell/.NET C#
interop facility; application remains Windows native, no required Docker/WSL or
Python runtime service. Constrained-language environments may fail before action.
Ordinary supported identity, permissions, N47P journal semantics and installed
Hook/EXE are unchanged. Concurrent adversarial directory replacement or case-flag
changes after checks remain a TOCTOU limit, not solved by this guard. Do not
change original C++/schema/ledger/test assertions or create a Release. Revert the
installer guard for code rollback; no data migration is needed. Existing paths
newly rejected require an explicit inspected recovery, never silent flag changes.
