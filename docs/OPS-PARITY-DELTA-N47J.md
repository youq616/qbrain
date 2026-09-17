# N47J capability delta

Actual product: 2ec0c3daaa6d324bcc9f16a1ebacc88c63abe561, tree
37cfb0d5bd1df6501f0a42fe19d253e0e9e8b431. Required native runs35163779907 and
35163779904 passed; outcome in N47J-HARD-AUDIT.md. Publication is separate.

Added bounded diagnostic checkpoints per allowed host/event, retaining legacy
last-trace. Two fixed hosts by five fixed events, ten slots, <=4096 bytes each.
Records use a closed metadata projection and pseudonymous session correlation,
not original prompt/answer/context, raw identities, exception messages or secrets.
A scope-bound recorder under the runtime lock distinguishes accepted processing
failure phases; each replacement is independent and best effort.

The omitted forgotten capture enum is repaired. Local replay records failed/extract;
deferred replay can complete with capture_status=forgotten. Neither recreates
forgotten evidence or establishes model consumption. Old tombstone semantics stay.

No schema, MCP name, collection/promotion permission, model request or installer
change. Exact native registry is58; metadata9/169 and Hook process66/80 passed.
Not an unlimited audit history, power-loss guarantee, new live-host acceptance,
privacy enforcement against a hostile filesystem owner or entire-project finish.
