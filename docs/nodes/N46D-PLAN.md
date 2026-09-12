# N46D — embedding response contracts and model-scoped retrieval

Status: done for scoped N46D after N46D-QUEUE-HARD-AUDIT.md; owner-authorized self-review replaces external review. Baseline: youq616/qbrain @ 93f80b64756ee520885d8d890bfecfc36eb6af7f.
Windows native C++20 only. No runtime services, database migrations or paid calls.

## Scope and acceptance

1. Validate embedding responses before exposing any vectors: exact requested
   item count, unique integral indices in range, consistent nonempty dimensions,
   finite representable nonzero float vectors, explicit float encoding, bounded
   response bytes/nesting/dimensions/items. A bad item rejects the whole response;
   no partial vectors or provider body/parse excerpt in error output.
2. Keep request model identity authoritative: optional response model must match
   the configured requested name exactly. A missing response model uses that
   request name for existing compatible gateways. Do not silently infer aliases.
3. Production hybrid search (search and think) defaults to the active embedding
   model (or the explicitly enabled mock model), with exact stored model and
   dimension predicates in addition to existing source/deletion checks.
   Low-level raw vector callers may supply an explicit model; the legacy raw API
   remains available for tests/expert code. No new CLI/MCP bypass flag.
4. Images reuse the validator, require one vector and enforce their existing
   2 MiB cap inside the shared transport, not only after download. No image-model
   quality or source-scoped file permission expansion.
5. Fix the existing N42 test adapter's missing canonical_source_id/bind_null and
   links.id schema; retain its SQLite adapter tests and execute them in the main
   validation workflow so future regressions are not missed by branch-only CI.
6. Add exact named unit group, real CLI/MCP source/model isolation tests using
   disposable brains, and Windows loopback tests using production embed_texts/
   embed_image for invalid responses, reordering and clean errors.
7. Retain all existing native HTTP/memory/context/hooks/PowerShell tests and the
   N46C benchmark; require new reports at the same-source package gate.

## Compatibility, privacy, rollback

This is model-label plus dimension matching, NOT provider/endpoint/version
attestation. A provider can reuse a label for different weights; that remains a
separate provenance task. Legacy unknown/different-model vectors are excluded
from vector ranking, but their pages remain eligible for lexical retrieval.
No automatic re-embedding/costs, destructive cleanup or new persistent cache.

A proxy returning a different model alias will be rejected; configure the exact
model name or explicitly re-embed outside this node. Bounds are local policy,
not claims about every upstream model's maximum token or vector size.
The mock is synthetic and not a semantic-quality model.

Work on optimization/n46d-embedding-contracts. Record real failures, exact source
and CI evidence. No successful previous run can certify changed production code.
Rollback: revert code/tests/build changes; no database downgrade is needed.

Queue follow-up scope and amendment: [N46D-QUEUE-PLAN.md](N46D-QUEUE-PLAN.md).
