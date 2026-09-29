# N48O parity delta — PostgreSQL session memory only

Existing session capture/extract/read/status/drain/forget now have an explicitly
opted-in PostgreSQL implementation. This adds no MCP operation or registry count;
default write/source denials and SQLite behavior stay intact. Qualified504f2825
has native PostgreSQL and SQLite evidence plus complete-source binding and separate
self-review. See [outcome](nodes/N48O-HARD-AUDIT.md). No fact_store/context/Hook or
all-PG parity is inferred. A shared DSN is not isolated by changing brain labels.
Real client/model, signing/stable, release and Issue40 remain separate gates.
