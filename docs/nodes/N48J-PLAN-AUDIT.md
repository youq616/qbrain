# N48J design review

2026-09-26. Coordinator self-review of the explicit design, before publishing a
candidate. This is not a third-party review or an outcome acceptance verdict.

The module must bridge existing execution evidence rather than introduce another
pricing algorithm. N47S receipts lose cache partition detail, so original response
bytes must be bound and only a named accounting projection sent to unchanged N48G.
Completed response parsing must match the original executor; unknown/failed usage
cannot be reconstructed from lossy receipt totals. N48I already supplies exact
comparison and model/price/unknown eligibility; do not fork it in Python.

Reject silently dropping failed requests, inventing calls for unattempted rows,
relabeling loopback tests as provider measurements, or claiming main-only results
are full-pipeline savings. Require explicit main-only scope in the price document.
Do not open the answer key or invoke the execute/scoring stage. Existing paid-call
approval and capture permissions are outside this read-only adapter.

Source and output paths are separated, strict regular-file/link and inventory
checks are required, exact deterministic bytes and source/tool/binary provenance
are retained, and readback must recompute rather than trust the saved manifest.
Concurrency rechecks reduce ordinary mutation errors but are not a hostile OS
filesystem sandbox. The explicit executable is trusted; no arbitrary executable
security guarantee is possible from file hashes alone.

Design disposition: implement and test this bounded contract. Outcome acceptance
requires new Windows/Linux execution of the actual adapter and its tests, retained
native/acceptance regression, and separate post-implementation review.
