# N48R design review

2026-09-29. Owner-authorized coordinator separate design review: APPROVED.
Reviewed Hook, FactStore ReadScope/WriteScope, session source check, Brain PG open
and backend lifecycle. Merely removing brain.db is insufficient: sqlite_master fails
on PG, FactStore refuses Hook's caller transaction, and session read refuses any
active transaction. Avoid globally allowing nested reads/writes. The new private
reader requires a live owned PG fact scope plus server-confirmed repeatable-read
and read-only settings; normal session APIs remain strict. Hook entry requires idle
state. Internal existing-only Hook opening must validate public/UTF8 and relevant core table
resolution before reading config, never migrate on Hook invocation. Effective PG
identity must bind deduplication state without leaking DSN/password.

Risks and tests: nested ownership escape -> caller/write-scope negative probes;
missing source -> no DDL/fallback; retired facts reappearing via memory lane -> exact
quote suppression checks; late capture -> finish snapshot first; errors -> single
empty fail-open JSON, trace projection unchanged. Application statement timeout is
bounded on the Hook PG connection, but no hard OS/network wall-clock guarantee.
Original PowerShell host-process supervision is unchanged. Not model quality,
secret-scanning/DLP, hostile DB-owner isolation, or stable-release acceptance.
