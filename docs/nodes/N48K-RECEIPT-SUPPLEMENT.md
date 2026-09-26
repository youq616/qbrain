# N48K preexisting-receipt review supplement

2026-09-26. Parent f261896e, immutable package SHA256
58d56b7bd7c9a662514e41d20bacb88c68c92bbe3fc380496a09331bf1f5cafa.

Separate review found a coverage gap: the original upgrade script creates its
receipt AFTER upgrade. It establishes preservation of old facts and new receipt
history on uninstall, not preservation of PREEXISTING receipts across upgrade.
This is a missing acceptance probe, not evidence of product data loss.

Add a separate source-pinned native Windows job on the already-qualified unchanged
ZIP. With each PowerShell 5/7 and each Claude/Codex integration, create a fact plus
one active and one withdrawn receipt using the OLD N47X EXE, then upgrade, roll back,
upgrade again, and uninstall. Compare full fact, usage summary, all/current/withdrawn
receipt snapshots at every stage; verify unrelated configuration and global default
brain preservation, and duplicate reporting remains idempotent. Save every CLI
request/response/exit and each before/after snapshot. No private brain or live agent.

Preserve original tests and package bytes; do not recompile or silently patch the
accepted ZIP. The old full native/packaging evidence remains pinned to f261896e;
this supplement must obtain its own new native execution before final acceptance.
Only repository contents/actions read permissions are used to retrieve the pinned
original artifact. No Release/tag or security-setting changes. Local Linux ledger
fixture runs explicitly do not execute installers and cannot close this gate.
