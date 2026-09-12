# Embedding queue repairs (N46D continuation)

Both Brain::drain_embed_jobs and the generic jobs worker use the same production
implementation. An automatic drain returns committed chunks across its invocation;
a generic drain still returns processed jobs. Job result_json.chunks counts only
committed rows in that job's current attempt, never the invocation total. A retry
starts a new attempt count and requests only still-missing chunks.

## Batching and outcomes

Each request obeys the existing 2048-input, 32 MiB serialized JSON and parser
value/dimension limits. A conservative value budget also reserves response space.
Unknown dimensions use the 16384-dimension worst case; this can cause more, smaller
requests. JSON escaping (including quotes, controls and embedded NUL) is included
in byte limits. Oversized single chunks and invalid UTF-8 fail before dispatch.
Nothing is truncated or silently relabelled.

Deleted/missing pages are cancelled. A changed/rechunked page or a changed chunk
fails with outcome=stale; retry is explicit. Already committed batches are retained
if a later request fails. Every batch and its progress update share one transaction;
a stale or failed current-batch write rolls back that whole batch. chunks counts
writes actually committed by the attempt, not rows guaranteed to survive a later
user deletion. No complete status is recorded while missing work remains.

## Ownership and concurrency

Jobs are claimed with tokens/attempts and a lease. Both persistence and status
updates check the active claim, attempt and unexpired lease. The lease renews before
each request; paused, cancelled, expired or reassigned work cannot be revived by a
late response. Automatic and generic workers cannot process the same live claim.
Distinct jobs for the same page can still make duplicate provider calls; conflicting
results are discarded rather than overwriting a newer vector.

Page/source/content and chunk-set identity are checked before each request and in
a short transaction before persistence; exact chunk text/index are checked by the
conditional writes. There is no open SQL statement or transaction across provider
I/O. An edit/delete after the last preflight can still occur after transmission
starts: the late result is discarded, but already sent bytes cannot be recalled.
There is no exactly-once billing promise after process crashes or lease expiry.

SQLite uses short BEGIN IMMEDIATE transactions. The PostgreSQL compatibility path
uses short page/chunk table locks; it is not certified PG performance or integration
coverage. Schema, provider permissions and MCP write policy are unchanged.

CI tests execute the real C++ queues, migrations, SQLite and embedding parser with
only HTTP replaced by a deterministic in-process provider. They include native
Windows execution but are not real paid model calls or Win11 signed-in Agent tests.
Existing native WinHTTP wire fixtures remain separate and must also pass.
