# N47S separate outcome review findings

2026-09-19. Same coordinating assistant, separate engineering review, not another
agent. Initial candidate7024ee2 passed its43 tests and fixed CI35432671949, but
later adversarial review found two boundaries requiring repair before acceptance.

1. Explicit endpoint port0 used Python `or` fallback and could silently target the
   default port. Distinguish omitted from zero, then reject zero before output or
   network. Both HTTPS and loopback cases reproduce the old behavior.
2. HTTPResponse.read1 can return EOF with a valid JSON prefix although the declared
   Content-Length has not been received. The initial runner accepted that response
   and continued the100-call plan. Check framing headers and exact declared body
   length; reject duplicate lengths and mixed Transfer-Encoding/Content-Length too.
   A valid JSON prefix is not sufficient proof of complete transport delivery.

A separate two-method real-loopback test file was run against the exact original
7024ee2 module bytes: four failing subcases, zero test errors. The repaired module
passes the same tests; original43 methods are unchanged and all45 methods pass
normally and with Python-O locally. Four failed subcases describe overlapping
variants of the two findings, not four independent vulnerabilities. The baseline
rejection uses no external provider and carries no actual model result.

No original N47Q test, case denominator, model consent, TLS check or request limit
was weakened. Failed network calls stop all remaining requests without retries.
Final Windows/Linux validation must run on the repaired commit; the earlier green
run is not the acceptance basis for this repair. A malformed root report is also
explicitly rejected instead of causing an unhandled attribute lookup.
