# N46B — bounded Windows model transport
Status: done for the scoped N46B transport node after N46B-HARD-AUDIT.md.
Not a full-project, signed-production, live-model or Win11 host acceptance claim.
Baseline: youq616/qbrain @ 380524b8506e4b333613eb830bae8fd002f4b3ae.
This node belongs only to the native Windows Qbrain project.

## Scope
Close the outstanding HTTP transport boundary in issue #2 / N46. Keep C++20,
WinHTTP, the existing SQLite memory/context architecture, PowerShell installation,
and all existing provider-consent and MCP write gates. No database migrations,
new required services, paid provider calls, credentials, or upstream source merges.

## Deliverables and falsifiable acceptance
1. One steady-clock deadline shared by send, headers, and every body read.
   Async WinHTTP waits are cancelled at the deadline; phase/packet arrivals must
   not reset it. This is a bounded network wait, not a hard-real-time OS guarantee.
2. Fixed 16 KiB receive buffer. Default response cap 8 MiB; callers may explicitly
   choose 1 byte through 64 MiB. Reject over-cap declared or streamed bodies.
   Reject outbound bodies above 32 MiB before narrowing lengths to WinHTTP DWORD.
3. Read/connection/timeout/length errors discard partial bodies and cannot expose
   a successful 2xx response to existing consumers. Classify failure explicitly.
4. Reject malformed URLs, URL userinfo, control characters, invalid UTF-8 and
   bearer-header injection before network I/O. Join root and prefixed paths once.
   Disable automatic redirects, automatic authentication and cookie handling;
   preserve system TLS certificate checks. Configured HTTP remains supported
   for local providers; remote providers should be configured with HTTPS.
5. No provider body, token or request text in transport error strings. Non-2xx
   responses have status-only errors and no returned body.
6. WinHTTP callback context plus outbound/receive buffers survive cancellation
   until HANDLE_CLOSING. RAII closes request, connection and session handles.
   Callbacks only signal completion; they never recursively launch reads.
7. Test the production transport against a loopback fixture on a native Windows
   runner: normal JSON/Unicode/path joins, empty/exact-limit/oversized/chunked,
   stalled headers/body, trickle timeout, disconnect, redirects, error redaction,
   repeated cancellation and concurrent independent requests. No real model API.
8. Run existing memory/context/MCP/Hook and Windows native regression. Preserve
   verification log checks; do not equate Linux stubs with Windows HTTP coverage.

## Ledger and compatibility
No new MCP operations. Update the N46 transport row and node evidence only.
Existing callers retain the default timeout/cap. Chat timeout classification uses
transport evidence instead of an elapsed-time heuristic. Rejected redirected or
oversized endpoints must be reconfigured, not silently retried without limits.

## Rollback and evidence
Revert this node's code/build/test changes; no stored-data format change.
Work on optimization/n46b-http-boundaries; keep main at the baseline until native
checks pass. Record exact commit and Actions IDs; do not label a node complete
while native execution is unverified. Unsigned preview is not a production release.
