# N46F: eliminate per-request session churn

Scope design review: accepted for implementation by ChatGPT under owner authority,
not external review. Native outcome is pending. Base source is 9a36f8cc.

## Evidence and rejected hypotheses
Retaining parents alone failed 34760027604. Private pooling failed 34761621589 and
was unsupported on Server 2022 (12009), proven by no-network option observations
34761999517. Resolver timing changes in 34762326483 did not reliably stay within
the original +16 ceiling. Do not promote any of these as the final repair.
PSS aggregate-only diagnostic 34762624868 localized the growing objects to Events,
not file/connection handles; explicit application-owned handles and states balanced.
Its Server 2022 observation completed and failed the original ceiling; the other
matrix job was cancelled by fail-fast, not counted as a successful observation.

Controlled experiment 34762949138 compared unchanged retained-parent per-call
sessions with one immutable shared session and per-request timeout settings.
Server 2022 original 175->194, shared 174->174 and 168->168. Server 2025 original
170->200, shared 167->167 and 161->161. Each variant used 8x32 cancellations with
fixed 250/2000ms observations. Shared runs correctly retained one explicitly owned
session; they were diagnostic observations, not product acceptance.

## Selected implementation and review gates
Use one process-owned session with thread-safe initialization; failed initialization
is not cached. No caller-specific header, cookie, token, body or timeout is stored
on this shared object. Every call owns connection/request handles and callback
state. Set timeouts on request handles and retain the shared parent until final
callback. Normal process teardown releases the cache. Do not weaken TLS, source,
consent, redirect or response-size protections. Remove unsupported private-pool
option completely rather than silently taking an untested compatibility path.

Keep the unchanged +16 process growth ceiling, fixed 8x32 rounds and two separate
current processes. Explicit diagnostic cache release must close the final retained
session after all request owners are gone. Reports distinguish one cached session
from unclosed per-request handles and reject missing shutdown evidence. Add real
parallel header/body/cookie/origin isolation and differing deadline tests. Both
Server 2022 and latest native HTTP jobs gate publication; all original product
regressions and CJK tests remain required. No retry-until-green loop.

## Limits and rollback
Proxy defaults are captured at session initialization; process restart is required
after changing them. No persistent cache of user content or credentials is added.
The experiment attributes growth to per-call session churn, not a proven internal
Windows bug or universal leak-freedom theorem. A bounded shared session is deliberate
ownership, with shutdown verified independently. Revert source/tests/workflow to
roll back; no database or global OS configuration is changed. N47 is untouched.

Primary documentation consulted:
https://learn.microsoft.com/en-us/windows/win32/winhttp/concurrency-in-winhttp
https://learn.microsoft.com/en-us/windows/win32/winhttp/winhttp-sessions-overview
