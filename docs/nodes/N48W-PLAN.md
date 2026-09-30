# N48W — metadata-only runtime model HTTP observations

2026-09-30. Base e0a27f829d970c24ed8c566023ada0911c0042b3/tree534c86de.
Status: approved after N48W-PLAN-AUDIT.md. Original Issue2/N46 requires actual call
usage rather than only caller-written ledgers. Existing N48F/G/H/J/L calculate or
import records; chat_complete exposes only two totals and embed/native rerank no
shared ledger. This slice observes the shared http_post_json boundary for the
running process. It is not whole-pipeline billing, stage attribution or model quality.

## Contract

Add explicit `qbrain observe --output NEW_DIRECTORY -- EXISTING_COMMAND ...`.
No opt-in means no collector, file, provider, request parsing or usage extraction.
The selected command runs normally with original stdout/stderr; only the observation
sidecar excludes all command arguments, prompts, replies, endpoints, models, API keys,
response IDs, error bodies and hashes of these private strings. Only fixed enums,
sequence numbers, numeric usage/status/elapsed time and counts may be persisted.
Underlying command output is outside this sidecar guarantee.

Record a start before each HTTP invocation and completion after it; bounded512 retained
attempts, overflow and logging failure mean incomplete, never fabricated zero. A
process killed mid-call leaves a start without completion, NOT proof of cancellation.
Transport send invocation is distinguished from server receipt/billing. Unsupported,
invalid, HTTP error, timeout, explicit transport cancellation, thrown exception and
pending are distinct. Every repeated boundary call is retained; retry identity/count
is unknown unless the caller supplies an external assignment. No prompt comparison,
response-id matching, auto-retry or hidden request is introduced.

Normalize only completed bounded JSON response usage. Reuse N48G's strict known
OpenAI Chat/Responses disjoint-bucket rules; embedding inclusive input can be observed
but unsupported cache partition remains unknown. Unknown/invalid/duplicate-key/large
usage remains unknown, not zero. Failure body already suppressed by the original
transport stays suppressed. No inference of application success from HTTP200.

Runtime cost has no currency/rate by default and stays null. A separate offline
`observe cost --report PATH --assignments PATH` requires exactly one assignment for
every retained invocation, uses observed tokens/outcomes (not overridden), and reuses
N48F exact arithmetic. Unknown usage/rates/outcome and incomplete capture remain
explicit; never price only a favorable subset. Model/price applicability and logical
retry labels are caller declarations, not authenticated from private metadata that
we deliberately do not retain. No current price lookup or invoice claim.

Collector mutex must never cover a network call. Process-wide opt-in captures calls
from worker threads; completion after sealing cannot change a finalized report.
Invalid nested observation refuses. Sidecar I/O failures do not retry or relabel a
successful provider call, but the observe wrapper fails its evidence gate. Exclusive
new-directory/new-file output reuses existing N48M path/I/O helpers. Filesystem
hostile concurrency and memory/pagefile erasure are not promised.

## Validation and isolation

Exact counter/usage tests, missing/cache/contradictory/invalid JSON, failures/repeated
calls/cancel/timeout/pending, cap/late completion/concurrency/logging failure, no-content
sentinels, pricing all-record assignment/unknown rates; actual existing API wrapper
and unchanged HTTP contract tests. Windows numeric-loopback chat/embedding/native
rerank calls with count/response/status fixtures; real CLI observe/no-overwrite and
SIGKILL-like child termination produce start-only evidence. No real provider/account.
Fresh native Windows/Linux, sanitizer and original regressions bound to new SHA.
Author tests/CI are not the new non-author review; keep that gate pending until received.

Separate feature/n48w-runtime-observation based on merged main. Do not change any
PR61/62/63/d57 candidate, the frozen tests/test_pg_directory_cache.cpp upload or its
contents by any route. No merge/deploy/force push/new runtime package. Preserve failure
logs and recoverable patch. Root build and unrelated workflows stay unchanged.
