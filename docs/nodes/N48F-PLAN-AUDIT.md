# N48F separate plan review

2026-09-22. Reviewer: coordinating ChatGPT in a separate engineering planning pass
under the owner's current explicit self-review instruction; not another agent or
third party. APPROVED for the bounded opt-in query-embedding cache scope.

The roadmap calls for query/embedding caching. Cache embeddings, not database
search hits: otherwise forget/delete/permission changes can serve stale evidence.
Per-Brain ownership and resolved-source keys prevent cross-source reuse. Provider,
endpoint, model, dimensions, resolved credentials and mock mode belong to the
policy identity. Config/close resets and generation tokens must reject late insertions;
merely including a different key is insufficient for a disabled-then-enabled cache.

A single mutex protects slots and accounting, never provider work. Do not introduce
per-key blocking promises, infinite waits or hidden retries. Duplicate concurrent
loads are explicitly allowed. Fixed slot and retained-payload limits must hold at
all observable states, including replacement and exception paths. A cache hit must
return an independent copy. TTL uses steady time and cannot be prolonged by reads.

Default opt-out, per-query local-key check and unchanged default provider behavior
preserve current permission/egress boundaries. No indexing, image, result, user-data
or credential persistence is authorized. A provider may vary inside the TTL; opt-in
and short non-sliding lifetime are an explicit consistency tradeoff, not proof of
model determinism. Clearing does not promise zeroed allocator pages.

Native evidence must include actual registered search against changing database
contents, not only an isolated LRU unit. Baseline/raw outputs, errors, dimension and
credential changes, policy resets during outstanding loads, exact TTL and resource
limits are mandatory. Windows transport measurements, if run, are loopback fixtures
rather than real provider costs. Existing gates remain; build/source identity must
be read back before merge. No platform result or savings number is accepted early.

Primary C++ draft references for the implementation choices:
https://eel.is/c++draft/time.clock.steady
https://eel.is/c++draft/thread.mutex.requirements.mutex
These establish monotonic-clock/lock semantics, not proof of the proposed algorithm.