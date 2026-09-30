# N48V separate preimplementation design review

2026-09-30. Reviewer: owner-authorized coordinator engineering self-review, not a non-author or subagent.
Disposition: PASS to implement the bounded plan; no outcome acceptance yet.

Read the old49edf765 cache plan, current Brain lifecycle/config and credential resolver, embedding validation/mock policy, exact registered search/think call sites and live hybrid retrieval. Both query calls follow the existing source resolver; altering only these two avoids caching indexing/image/batch embeddings. Reject process-global Brain-pointer maps (reopen/address reuse), raw-query/credential storage, result caching, wall-clock/sliding TTL and a mutex held across provider callbacks.

Require per-Brain ownership, policy digest/epoch fencing, copied results, exact finite/model/dimension validation and positive tests showing permitted provider loads still work. Revoking MCP source permission must deny BEFORE cache lookup. A same-query cache hit must still retrieve current pages; counters must never be called billing verification. No claim that provider model labels attest weights.

The three-file source recipe is constrained to exact reviewed base blobs and a dedicated feature branch. It must produce actual committed runtime sources before read-only native tests, retain a reversible patch and separate bootstrap/tested SHA. No changes to PR61, PR62, PR63, their tests or the denied PG test. No write capability or safety refusal is being bypassed for that action.

Earlier848 non-author PASS is user-provided and limited;18ab native success does not close missing migration tests. These facts are recorded in PR comments independently. This new module needs its own tests and eventually its own non-author review; do not inherit their acceptance. Full release qualification stays open.
