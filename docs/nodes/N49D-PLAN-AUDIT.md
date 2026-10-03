# N49D plan audit

**VERDICT: PASS**
Date: 2026-10-03 UTC
Review: separate engineering plan review, under the repository's owner-authorized independent review process
Accepted base: `cfe1ef58e244b51092c2248804b663b6c28913d7`
Accepted base tree: `75b69ad389630e51528ddb5536a27255203470df`
Original MCP technical plan SHA256: `df0d8a44cff5f6f920090020ea643560daa1c506e0f758134b9da6fad762595e`

The bounded technical plan passed review before implementation. The approved
repository plan retains that contract, with status updates and repository-facing
provenance wording. This is a plan approval, not native qualification, an outcome
PASS, third-party certification, or permission to merge/deploy.

## Checklist

- Goal: expose accepted directory search through the existing MCP search tool
- Scope: only the search handler/header addition and a search-specific URI type check
- Compatibility: preserve source conversion/authorization, no-URI behavior, response shape, tool sets, and write denial
- Error layers: preserve malformed JSON envelope errors; validate decoded URI values at the existing tool/handler layer
- Tests: explicit twelve-test native selection, both Windows canonical suites, actual stdio and Windows HTTP, CLI equivalence, ordinary regressions, and ASan/UBSan
- Evidence: exact candidate/tree binding, bounded raw diagnostics, immutable binary identities, finite negative controls, and measured artifact limits
- Platform: native Windows C++20 remains required; Linux HTTP stubs cannot count as actual transport evidence
- Ledger: a bounded note on the existing search row, with native outcome pending
- Dependencies/security: unchanged directory/CLI/ranking/cache/auth helpers, disposable SQLite and mocks only, no real data or paid calls

## Findings resolved before approval

Three initial P1 clarifications were resolved: exact legacy source/error-layer and
no-vector semantics; effective assertion-preserving sanitizer Debug flags and
measured artifact caps; and finite fail-closed tests for the new recorder,
packaging wrapper, and bounded consumer. No P0 or P1 finding remains in the
approved plan. Implementation and native evidence still require outcome review.

## Outcome gate

The candidate must keep its native/outcome status pending until all current-node
obligations pass and the exact frozen commit/tree receives a separate outcome
review. Final acceptance is recorded externally for that exact candidate; a
later documentation commit cannot silently inherit its native PASS.


## Version 2 build-phase amendment

The separate plan review approved an explicit trusted-build contract for exactly five Windows compiler/configuration stage pairs, with strict ownership for every product test and other default caller. The direct-MSVC wrapper separates compilation and canonical execution while preserving default behavior, runtime context, real exits and the original combined deadline.

The reviewed conditions include exact-zero/high-bit error handling, fixed object and binary continuity, configure readiness, one-attempt owned-job cleanup, accurate failed facts, acyclic versioned reports, bounded complete retention and producer/package/consumer agreement. The source scope adds only the two ordinary inherited wrappers to the prior accepted-base delta; the product implementation remains restricted to its original two regions.

The plan accepts the declared trusted compiler-root assumption, not a claim about an auxiliary process's benignness. Existing failed outcomes remain failed. Actual Windows behavior, default-dispatcher coverage, serializer/timing/source/archive fit, exact-source review and all four native jobs remain required before outcome acceptance. The implementation and public status stay pending that evidence.

The failed-control encoding amendment preserves all control facts and stream limits. Native qualification remains pending.

The aggregate-admission amendment requires complete LF and CRLF metadata/total prewrite checks. Selected-fact retention is conditional; rejection is incomplete/HOLD. Original errors are reported before optional persistence, separately from record/collector failures. Real caller, boundary, unchanged-destination and storage controls are required in both Python modes; source/native outcome remains pending.
