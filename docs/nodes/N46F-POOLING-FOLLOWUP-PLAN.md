# N46F follow-up: session-private connection pools

Status: scoped design review accepted for implementation by ChatGPT under the
owner's authorization; native outcome pending. This is self-review, not external
or third-party approval. Baseline: dcf8d45eaf83cc8090d527489a4944efccb5bddd.

## Evidence requiring further repair
Run 34760027604 failed: retained parents still grew process handles 172 -> 205
over 256 cancellations, exceeding the unchanged +16 ceiling. Every explicit
WinHTTP handle and AsyncState had been released. Parent lifetime alone is therefore
not a sufficient explanation or verified repair. Do not rerun unchanged code until
a passing sample occurs. Preserve this run and earlier 34753274282/34759394490.

## Change and controlled test
WinHTTP retains legacy cross-session connection pooling by default. Use
WINHTTP_OPTION_DISABLE_GLOBAL_POOLING on each Qbrain session before children are
created. Microsoft recommends disabling this legacy behavior. Require option setup
to succeed, keep parent ownership through the final callback, and retain all
deadline, response cap, credential and redirect protections. No global setting,
registry mutation, environment switch, new persistent session or TLS relaxation.

Add a diagnostic-only pooled-parent control to separate pooling from early parent
closure. Compare early-parent/global-pool, retained-parent/global-pool and the new
retained-parent/private-pool implementation using a fixed schedule. Execute the
new variant twice in separate processes; both must pass independently. The
original +16 ceiling and 250/2000 ms observation times remain, with no retry loop.

Validate the complete lifecycle report independently: exact rounds/counts,
ownership balances, final callbacks, source/probe hashes, all timeout results,
finite numeric fields and both current runs. Negative tests must reject empty,
partial, stale, wrong-binary or internally inconsistent reports.

## Compatibility and limits
Calls already have their own session; disabling cross-session pooling may lose
connection/TLS reuse across requests and increase handshake overhead. This node
does not claim endpoint latency improvements or universal OS leak freedom.
Unsupported option setup returns a transport error rather than silently reverting.
Do not confuse session-private pooling with disabling TLS/authentication checks.
The scoped test is synthetic loopback; real TLS/proxy/host performance is untested.
No CJK production logic, schema, provider consent or MCP authorization change.

Reference (consulted September 13, 2026):
https://learn.microsoft.com/en-us/windows/win32/winhttp/option-flags
