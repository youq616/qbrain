# N48Q pre-implementation design review

2026-09-29. Reviewer: ChatGPT, owner-authorized separate coordinator self-review.
Decision: PASS for implementation, not outcome acceptance or third-party review.

Inspected fact_store.cpp, fact_usage/read/batch headers, SQLite snapshot/authorizer
contracts and N48O/P PostgreSQL helpers. A generic global SQL rewrite or permissive
transaction reuse would weaken prior guarantees. Use a private fact-only dialect
adapter and connection/thread-local RAII ownership to allow internal read composition
while refusing external transactions; keep original SQLite authorizer-visible SQL.
Require canonical public relations/cleanup and fixed writer lock ordering, test
last-support cascades and stale receipts, reject unknown layouts. Keep full-evidence
and revision rules; do not turn explicit facts into inferred truth or auto-resolve
conflicts. Native real-PG tests are mandatory before module outcome acceptance.

Risks: concurrent deletion/promotion -> serialized core locks plus revalidation;
nested reads -> owned-scope marker with RAII teardown; typed PG vs corrupt SQLite ->
backend-specific probes and unchanged SQLite paths; cleanup trigger mismatch ->
strict function/trigger checks; missing environment -> explicit unclosed gate.
Scope is bounded existing functionality; no external model or client claim follows.
