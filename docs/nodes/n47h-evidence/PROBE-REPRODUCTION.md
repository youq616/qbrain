# Supplemental paging probe reproduction

This is outcome-review tooling, not a new product target. Compile against the
unchanged product80fe1b9d31de6cc41d06be6db0e1035c1a747eb7, source tree
5d17b1f68344d1c6370d4a113fddf5def1dc0e63. Source/report SHA256 are in SUMMARY.json.

In a separate Linux checkout configure CMake with QBRAIN_WITH_PG=OFF and build
qbrain_lifecycle_candidate_tests. Compile pagination_oracle.cpp with C++20 and
repository-root/include/third_party/third_party/sqlite3 include paths. Reuse the
same ordered static-library list as `ninja -t commands qbrain_lifecycle_candidate_tests`,
replacing the test object and output with this probe. Do not define
QBRAIN_CANDIDATE_STANDALONE: the probe has its own main. Invoke it with a new JSON
report path. This is a reproduction recipe, not a task requiring local setup.

The probe includes the original test file to reuse only fixture helpers and
assertion reporting; it does not invoke test_n47h. It maintains its own model
for liveness, archive status, newest valid support time and expected revision.
Source identity in output is the fixed compile input, not runtime Git detection.
Setup332 plus three scenario11775 assertions equal12107, not12107 unique business
situations. Each enumerated page call enforces source, order, count, byte bounds,
batch metadata and an exact independently expected full result set.

Synthetic ages and deliberate quote corruption are fixture preparation, not
normal user APIs or real old personal sessions. The apply phase uses explicit
production preview/apply calls and then verifies seek continuation through its
own changes. Counts:288 modeled claims,46 complete traversals,695 page calls.
Unchanged static data completeness is checked; concurrent earlier-ID insertions
are deliberately not claimed to be included in a stable multi-page snapshot.

A separate temporary production copy was also compiled with `consumed=id` inserted
before the output-budget stop. Original unit execution returned1 at the expected
cursor assertion. This copy was discarded from product integration; the reviewed
source tree and original test files remained unchanged. No additional Windows,
authenticated client, provider experiment or million-event benchmark is claimed.
