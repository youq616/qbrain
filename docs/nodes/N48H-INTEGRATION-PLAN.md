# N48H integration plan and pre-implementation review

2026-09-25. Scope approved by the owner: complete the existing module and perform a
separate self-review. Baseline 817d222a727bfe190f6ea0ee66d08eb61a0624b4, tree
0481139c8c17372af126e24a004dd15a0045cd7b. This is the remote repaired implementation,
not the divergent local e8a5c77c snapshot from the preceding delivery.

Preserve all product bytes, the remote 47-check direct suite and 543-case review,
and the original Windows/Linux workflow file byte-for-byte. A separate supplemental
workflow builds the full native product and runs the additional matrix on both OSes. Integrate the earlier 711-case
independent history/unknown-state oracle and its separate 47-check native target.
Do not overwrite the accounting header with the old full patch. Keep synthetic
examples and document source versus N47X release boundaries.

During intake the inherited supplementary evidence checker accepted two controlled
corruptions: False in place of a zero token count and a duplicate top-level JSON
key. Preserve the before-checker inputs and source identity. Tighten JSON parsing,
JSON type equality, exact report/row inventories, and raw-file inventories; add
explicit mutation tests without changing the deterministic 711-case product matrix.
This is test-tool hardening, not another product undercount defect.

Acceptance: local whole-program 711-case runs in both Python modes, all original
readback gates, native direct tests and sanitizers, then fresh Windows/Linux CI
bound to the integrated commit. Independently re-read raw outputs and exact source
archives, including CRLF identity on Windows. Do not inherit local-only Windows
claims. Document pass/fail/remaining scope in a separate final audit. No release,
private brain, provider request, fee guess, signing or Issue40 closure is authorized
by these test results. Avoid force pushes; re-read the branch before fast-forward.
