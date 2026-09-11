# N46B — Windows HTTP transport outcome review

**Verdict: PASS for the scoped N46B node.** Review date: September 12, 2026, Asia/Seoul.
Auditor: ChatGPT, under the owner-delegated continuation documented in issue #2
and prior node reviews. This is self-review, not an independent or Claude Code audit.

## Provenance

Baseline: `380524b8506e4b333613eb830bae8fd002f4b3ae`.
Tested source: `2661e5205ba480c993210405d35c463efd8c6b6c`.
Tested tree: `99f6472036b4e3c809ca3952b56c934aac5edc6e`.
[PR #6](https://github.com/youq616/qbrain/pull/6) contains the change;
GitHub PR state is authoritative about merge status.

[Validation run 34626277700](https://github.com/youq616/qbrain/actions/runs/34626277700)
finished `completed / success` at 2026-09-11 17:24:20 UTC. Windows job
`103352080985`, portable job `103352081154`, and source job `103352081232`
all completed successfully. Every Windows build/test/package step passed.
The Windows runner was Windows Server 2025, not a signed-in Windows 11 user desktop.
Subsequent outcome documentation does not alter the tested source or package bytes.

## Approved-plan acceptance

| Plan item | Implementation and evidence | Outcome |
| --- | --- | --- |
| One network deadline | Shared steady-clock deadline, async completion waits; slow headers, stalled body and trickled data tested at 250 ms | PASS; final timings 251 / 250 / 250 ms |
| Bounded bytes | Fixed 16 KiB buffer, response default 8 MiB, explicit cap <=64 MiB, outbound JSON <=32 MiB; exact, oversized, chunked and huge-length fixtures | PASS |
| No partial success | Read error/timeout/oversize/length mismatch returns status zero and empty body; a truncated but valid JSON prefix cannot become a chat completion | PASS |
| Request boundaries | URL/userinfo/control/UTF-8/header checks; exact path joining; redirect, cookie and automatic-authentication disabling; TLS verification unchanged | PASS; 30 native input assertions plus wire fixtures |
| Redacted transport errors | Non-2xx status-only errors; no provider body returned; 429/auth/redirect fixtures | PASS within transport scope |
| Cancellation lifetime | State owns outgoing/receive buffers until HANDLE_CLOSING; callback only signals; 64 sequential cancellations and 12 mixed concurrent requests | PASS for tested stress; no universal leak-freedom claim |
| Native wire execution | Production WinHTTP and production chat, synthetic loopback server, no paid model credentials | 51 checks PASS |
| Existing regression | Windows application, all 45 exact registered groups, memory/MCP/hooks/context/config, both PowerShell versions | PASS; real PostgreSQL explicitly skipped |
| Deliverable integrity | Same-source package gate, isolated native startup, manifests, checksum readback, PE architecture checks | PASS; unsigned development package |

Complete counts and individual HTTP checks are in
[n46b-evidence/RESULT.json](n46b-evidence/RESULT.json).

## Regression counts (do not sum nested groups as independent coverage)

Full native test entry point: **45 registered groups**, including the new HTTP group.
Within it: memory 85 assertions, context 37, native HTTP input 30. Separate production
process suites: memory 44, MCP boundaries 17, hooks 69, context 65, local configuration 6.
Each of PowerShell 5.1 and PowerShell 7: installer 69, consent/path identity 16,
byte-transport 8. Evidence-gate unit tests: 7. All passed in the same final run.
The historical real-DSN PostgreSQL integration emitted `[SKIP-PG]`; its enclosing
passing group does not certify PostgreSQL memory/context equivalence.

Portable CI also passed. Local focused CTest had 3/3 passing targets; local memory
82 and context 37 assertions are not a substitute for the Windows-only transport.
No new sanitizer coverage of async WinHTTP is claimed.

## Artifact readback

Windows logs artifact: `10275540036`; outer SHA-256
`275acf41adbb169acfb45e26dc8ed2c96352a02ad464e8c76a8faed797a2d7f4`.
Windows package artifact: `10275550042`; outer SHA-256
`79e6b00f18593793770006fd917d5646e3209ec91a4cff65b4859ac3af5cc67c`.
The **inner deliverable ZIP** is 1,830,806 bytes; SHA-256
`750b5835ad4c924365ba052aef2ed2e7482e0033558cdf84bf15db6b724f160b`.
The **EXE** is 3,800,064 bytes, PE32+ Windows x86-64; SHA-256
`b1cd89ec30f729ccaa0f83f1010cc15faf91b9148086c38c3a4bd34eb5fea0ce`.
No embedded Authenticode signature; no formal signed release was created here.
The earlier `memory-preview-5ee79dfd` Release does **not** contain N46B.

Independent readback performed 43 integrity/evidence checks. Delivered ZIP bytes
are the exact CI inner ZIP, not a reconstructed executable or repack. Both scripts
match repository contents after exactly LF-to-CRLF Windows checkout conversion;
there is no other content difference. They are not byte-identical to LF git blobs.
Their tested Windows bytes, manifest sizes and hashes were retained unchanged.
The 623-file source archive was separately matched against the intended source.

Cancellation handle counts were 197 then 199 after two 32-request batches, within
the explicit +16 process-handle tolerance. This is finite-sample evidence, not a
proof of zero leaks or zero lifetime bugs under every scheduler/proxy/OS condition.

## Defects and verification corrections during development

The new isolated HTTP/chat probe initially omitted static-library dependencies;
its real link failure was fixed by linking the complete existing production closure.
An archive readback found unintended test-helper and CMake-order serialization
changes; they were restored before the final tested commit. The new 45th group
required an explicit package-gate update. Negative tests now reject an old 44-group
log or a log missing `n46b_http`; no historical assertion was removed.

The independent verifier initially compared packaged Windows CRLF scripts with LF
archive bytes. It correctly flagged that mismatch. The verifier was corrected to
accept only the exact checkout conversion and record both hashes; package files
were not changed and a broad whitespace/content-normalization exception was not used.

## Remaining P2 limitations and compatibility

No open blocking P0/P1 was identified in this scoped review. Whole-application
ACL/DLP auditing, real providers/paid quality and cost, TLS/proxy/PAC fixtures,
hard-real-time OS scheduling guarantees, production signing, real logged-in Win11
Claude/Codex consumption, semantic conflict merging and PostgreSQL parity are not
certified by N46B. Issue #2 stays open.

The final API address must not depend on a redirect. Base URL query/userinfo and
non-ASCII/space/control-bearing bearer keys are rejected. The 32 MiB request limit
includes Base64 and JSON overhead: it is **not** a guarantee to transmit a 32 MiB
raw image. See [Chinese upgrade notes](../integration/N46B-UPGRADE.zh-CN.md) and
[transport details](../integration/HTTP-TRANSPORT.md).

No database schema/storage change, new required service, automatic provider consent,
new MCP operation or broadened write authority. Revert the node's code/build/test
changes to roll back; stored data formats do not require reverse migration.
