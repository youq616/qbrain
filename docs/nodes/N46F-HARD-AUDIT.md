# N46F outcome: CJK recall and bounded WinHTTP session ownership

Verdict: **PASS for scoped N46F delivery**. Reviewer: ChatGPT, separate engineering
review pass under the owner's recorded override. Not an independent third-party
or Claude Code audit. N47 and whole-project completion are not claimed.

## Provenance and completed execution

Baseline main: `48a498bbf2ea14b39f1023cd1d67e30fb98848f9`.
Actual tested source: `c665cb29cb44a6827670b8910b3d6adb568aa2c1`.
Actual tested tree: `555f08fc6fba20b39d764c8f2a7b0514f949b084`.
[Run 34765651987](https://github.com/youq616/qbrain/actions/runs/34765651987)
completed all source, portable, Windows, same-source Server 2022 HTTP and publication
jobs successfully. This includes the final package gate, not just compilation.
[PR #12](https://github.com/youq616/qbrain/pull/12) is the merge location; its GitHub
state determines whether the reviewed head has been merged.

Source artifact 10320101779 contained 685 files. Rebuilding its complete Git index
reproduced the tested tree above. Original local commits a0adf373/9426692 remain
preserved in the handoff; their code was not silently stacked with another CJK lane.
The final implementation uses one SQLite backend supplement and integrated,
corrected local regression cases. No production memory_read algorithm was changed.

## Acceptance against the plans

| Requirement | Observed evidence | Outcome |
| --- | --- | --- |
| Correct endpoint attribution | Original memory_read uses instr; noncontiguous spaced phrase is not a match. Ordinary search misses an in-token CJK substring before the repair | PASS; original misattribution corrected |
| Single literal supplement after indexed FTS | Valid CJK UTF-8, <=1024-byte query, bounded output, title/body/slug matches, deduplication, stable source-aware ordering and nearby excerpt | PASS; 72 native CJK unit checks |
| No scope or evidence relaxation | Actual CLI/MCP source denial, expiry, forgetting, tampering, no implicit traditional conversion, read-only checks and existing memory semantics | PASS; all 36 named process checks, 59 zero-exit child commands |
| Fail-closed evidence and Windows Unicode | Correct per-check counts, partial failure history, exact source/script/EXE binding; redirected stdout and default-codepage JSON reads tested | PASS; 10 CJK-report and 10 registry-gate unit tests |
| Cancellation ownership without unsupported options | One immutable session per process; per-request connection, timeout, bearer/body and callback state; parents retained through final callback | PASS on Server 2022 and Server 2025 fixtures |
| Session retention is explicit, not hidden leakage | Two fixed current processes, each 8x32 cancellations; +16 ceiling unchanged; all request handles/state/callbacks balanced; explicit final cache release | PASS on both OS versions; 14 report-gate tests |
| Existing product functionality | 48 exact registered groups, embedding/queue/retrieval/memory/MCP/hooks and both PowerShell suites; package startup | PASS, with explicit real-PG skip |
| Source-bound delivery | Versioned preview, original inner ZIP, per-file manifest and public asset digest/size | PASS; 87 separate artifact readback checks |

## Native counts and sample scope

Windows original regression: 48 named groups. CJK unit: 72 checks. CJK process:
36 checks / 59 child commands. HTTP wire: 81 on each Windows job. Embedding unit:
65, embedding wire: 26, embedding search: 11. Queue: 40 scenarios / 776 assertions.
Memory process: 44, MCP: 17, hooks: 69, context: 65, local configuration: 6.
PowerShell 5.1 and 7 each: installer 69, consent 16, byte transport 8. Counts
include nested/property assertions and must not be summed as unique user scenarios.
The original real PostgreSQL DSN cases explicitly emitted SKIP-PG.

The fixed lifecycle schedules each include legacy and per-call controls plus two
independent current processes. Each variant executes 256 cancellations; current
code therefore has 512 cancellations per OS in that diagnostic, not 1,024 unique
business scenarios. All current 2-second samples were constant:

| Platform | current / repeat | After explicit cache release |
| --- | --- | --- |
| Server 2025 | 167 / 161 | 166 / 160 |
| Server 2022 | 172 / 166 | 169 / 163 |

In the Server 2025 run the legacy control grew 175 -> 202; retained parents with
per-call sessions grew 168 -> 184. This supports removing per-call session churn
but does not identify every internal Windows object or prove universal leak
freedom. Tests use synthetic loopback, not the owner's actual model gateway.

## Failed approaches and failures retained

34753274282 failed the historical HTTP handle ceiling. 34759394490 then exposed
redirected Windows cp1252 output in the CJK report. 34760027604 disproved retaining
parents alone as a sufficient repair. 34761621589 and 34761769017 rejected the
private-pool approach; no-network observations 34761999517 showed the option was
unsupported on Server 2022. Resolver changes did not reliably fix growth; the
selected design is N46F-SHARED-SESSION-PLAN.md, not the superseded pooling plan.

34763772130 passed runtime tests but failed packaging because a report self-test
read UTF-8 JSON using the Windows default codepage. c665cb29 explicitly uses
UTF-8 and adds a forced-default-codepage regression. The final complete run uses
that changed source. No assertion, +16 ceiling or timeout was removed to pass.
All historical failed runs remain visible; no retry-until-green claim is made.

## Artifact readback and release

[Versioned release cjk-preview-c665cb29](https://github.com/youq616/qbrain/releases/tag/cjk-preview-c665cb29)
is public, a prerelease, and unsigned. It contains the unchanged tested inner ZIP,
SHA256SUMS.txt and PROVENANCE.json. Old N46E acceptance pins must not be changed to
pretend this new executable is the old 464045e2 package.

ZIP: 1,865,865 bytes; SHA-256
`d47918eb402692af9c3e4e332bf1f3faf0a86a71f49917dbc549fcf505bc217d`.
EXE: 3,823,616 bytes, PE32+ AMD64 without an embedded Authenticode signature;
SHA-256 `e5c77bb4f7852ac49fcac371e9944e386640220fa75099a0e01bd1fac82ab584`.

This continuation downloaded the source, original Windows logs, Server 2022 logs
and CI package. It verified their artifact digests, manifests, evidence identity,
exact Git tree and package/EXE hashes with 87 assertions. The downloaded inner ZIP
also matches the public Release API digest and size. The publishing job itself
downloaded and byte-compared all three release assets before publication; this
review does not falsely claim a second direct download of those release assets.
Packaged scripts match the source exactly or by exact LF-to-CRLF checkout only.
Diagnostic probe hashes are retained from reports; CI checked actual probe files,
which were not downloaded in this review. A separate local rerun of the 24 CJK
and lifecycle report-gate tests passed; no new local full C++/Windows run is claimed.

## Code review and limitations

The shared session is initialized under a mutex and is never modified with
caller-specific state. Timeouts are set on the request handle, not the session;
callbacks only signal completion. Requests/parents remain owned through final
callback and singleton shutdown. Cookie handling, automatic credentials and
redirect following remain disabled; TLS verification remains enabled. Microsoft
supports concurrent independent child handles and request-scoped timeout settings:
https://learn.microsoft.com/en-us/windows/win32/winhttp/concurrency-in-winhttp
https://learn.microsoft.com/en-us/windows/win32/api/winhttp/nf-winhttp-winhttpsettimeouts

Proxy defaults are captured at first session creation; restart the process after
changing system proxy defaults. Cancellation is a bounded network wait, not an
OS hard-real-time guarantee. The CJK supplement can scan selected-source pages;
500 results does not mean only 500 database rows scanned. There is no semantic
segmentation, synonym matching, traditional/simplified conversion, new ANN or PG
implementation. One cached session does not mean cached user prompts or credentials.

No blocking defect was identified in this scoped review. No data migration, new
MCP operation, automatic model consent or broader authorization. Rollback is a
source revert, not a database downgrade. The owner's Claude/Server2022 earlier
acceptance is separate from these tests; Codex credentials, live provider quality,
full ACL/DLP, signed Win11 distribution and N47 remain open.
