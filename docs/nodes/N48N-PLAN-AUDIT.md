# N48N separate plan audit

Reviewer: ChatGPT coordinator, owner-authorized self-review, not a third party or
subagent. This pass preceded implementation. Verdict: PASS for the bounded plan.

Scope fits Windows C++20 and adds a missing read-only FTS consistency diagnostic,
not a reimplementation of the mutating default-brain doctor. Main risks resolved:
(1) FTS check uses INSERT syntax: do it ONLY on the private memory snapshot;
(2) external-content verification requires rank=1, tested with a stale-index control;
(3) in-memory online backup requires the source page size before copying;
(4) schema mismatch and failed/omitted checks cannot result in success;
(5) no raw SQLite diagnostic strings, private text, SQL or source path in output;
(6) preserving original tests and platform-native qualification is mandatory;
(7) explicit source transaction limits writer-induced restart and mixed-state reads.

No P0/P1 design blocker found. Non-blocking limits are explicit: inventory is not
complete application semantics; SHM bookkeeping/OS paging and malicious concurrent
filesystem races are outside guarantees; monotonic budget cannot preempt all I/O.
Do not broaden PASS to runtime results, model/client gates, PG or stable release.

Pre-candidate re-review: approve the explicit WAL/SHM bookkeeping clarification.
The retained first process failure proves empty-WAL creation, not content mutation.
The revised assertion still rejects any change to preexisting main/WAL bytes or a
new nonempty WAL. A public true flag discloses the possibility. Do not describe this
as a byte-for-byte filesystem no-op; source business data remain read-only.
