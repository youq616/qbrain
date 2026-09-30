# N48X P2: retain move-only early return of rerank results

2026-09-30. Base b077cf3a46c21c858077c25a812f64481ab516c7,
tree c405ace53f00a77bcf16ba3ab7ded12757c9396b. Status: approved for repair.

The owner relayed a non-author product regression in 97b1: wrapping the reranker
in a reference-capturing observation lambda prevents the early return of the
outer results parameter from receiving the original implicit move. A disabled
nonempty call can now copy all SearchHits and throw bad_alloc even with observation
off. b077 only fixed the Windows newline expectation and inherits this runtime.
This differs from that preserved initial Windows fixture failure.

Fix only the existing early return to std::move(results). Do not change later
locally declared baseline/fallback returns, options, input/outputs, source checks,
observation classification, callbacks, permissions, error handling or signals.

Acceptance: full-length nonempty SearchHit values with heap-backed title/snippet
and spare vector capacity; prebuild all inputs, inject allocation failure only
around apply_reranker(std::move(hits)), then check success, zero allocation attempts,
vector/string buffer ownership, every field and callback/config bypass. Cover
!enabled, enabled with top_n_in==0 and top_n_in<0; also empty reserved input. Run
with observation off and separately with a preallocated in-memory observer. The
latter must still record disabled/empty_input with null model success, no HTTP,
no tokens/cost and no fallback. Calibrate fault injection with a real SearchHit
copy that must throw; collect output after the gate is disabled. Compile with the
real reranker object, not a replacement implementation. Original b077 must fail
the new contract and repaired code must pass. Preserve all original assertions.

Add a separate test executable so its global allocation hook cannot affect other
test binaries. Add it to existing N48X native and sanitizer target inventories
without lowering any assertion, deadline or test count. Bind source and artifact
identities to the new actual commit. Do not rerun/cancel prior queues or label
unexecuted Windows/native results as passed.

Separate design review: PASS to implement this bounded repair. Reviewer is the
owner-authorized coordinator; this is not the returned non-author outcome review.
The original completed d57/PR64 integration is read-only here. PR61/62/63/65 and the
frozen GitHub.create_blob -> tests/test_pg_directory_cache.cpp action remain
untouched. No merge, deployment, real data, paid provider or new toolkit. New
non-author review is still needed for the published repair; existing tests and
review records are not erased.
