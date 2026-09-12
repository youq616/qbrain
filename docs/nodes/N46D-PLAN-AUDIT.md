# N46D engineering plan review

Reviewer: ChatGPT, continuing the owner-accepted N46B/N46C development workflow.
This is an engineering self-review, not a Claude Code or independent audit.
Assessment: suitable for the scoped implementation; native outcome still pending.

- Exact input count must bound allocation; never resize from a provider index.
- Reject all vectors on any invalid item; a late invalid item cannot leak an
  earlier valid vector into a caller's persistence loop.
- Model filtering belongs in the shared hybrid path, covering both search and
  think without duplicating handler logic. Synthetic callers may pass their
  known model explicitly; the default must not fall back to wildcard matching.
- Match stored dimension metadata and actual decoded width. Maintain source,
  live-deletion and lexical fallback behavior. Do not mistake equal dimensions
  for equal coordinate spaces, or model labels for endpoint attestation.
- Negative fixtures must include fractional/huge/duplicate/missing indices,
  malformed JSON, float overflow, zero vectors, wrong model, and invalid UTF-8.
- Preserve independent N42 tests and add their execution to the development
  gate rather than removing the failing lane. No new dependency/service.
- Rollback requires no migration. Windows CI is not a logged-in Win11 desktop.

P0/P1 to resolve before delivery: parser all-or-nothing behavior, strict default
model selection, source isolation, existing and new native test gates.
P2: live providers, identical labels across endpoints/weights, re-embedding UX,
full cost/quality evaluation, PostgreSQL and independent audit remain separate.
