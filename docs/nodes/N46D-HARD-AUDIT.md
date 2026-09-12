# N46D engineering verification — independent audit pending

Required independent audit: **NOT PERFORMED**. This file is not an independent
or Claude Code audit PASS. Reviewer of the implementation and runtime evidence:
ChatGPT. The branch stays a draft PR; N46D is not marked done or merged.

## Provenance and actual execution

Baseline: `93f80b64756ee520885d8d890bfecfc36eb6af7f`.
Tested source: `6f88c073ad8332e0e629d3ab33ab6cd0b621451b`.
Tested tree: `c93e7d720fb3b866332a5682bef980de2f4be5b5`.
[PR #9](https://github.com/youq616/qbrain/pull/9) is the review location.
[Development run 34672404417](https://github.com/youq616/qbrain/actions/runs/34672404417)
and [N42 run 34672404422](https://github.com/youq616/qbrain/actions/runs/34672404422)
both completed successfully, including their Windows and portable jobs.
The development run completed at 2026-09-12T04:26:01Z. Subsequent documentation
changes do not change the tested runtime source, tests or build instructions.

## Engineering acceptance observations

| Planned requirement | Observed evidence |
| --- | --- |
| Complete indexed batches, bounded dimensions and constant errors | 65 unit checks; 26 native Windows wire checks using production text/image code |
| No cross-model production vector ranking | Default model, explicit model, stored dimension, source and deletion cases; 11 actual CLI/MCP checks including think |
| Lexical fallback and retained data | Other-model pages still searchable with FTS; all six fixture chunk records retained; no re-embedding jobs scheduled |
| Image 2 MiB transport cap | Oversized declared response rejected in native wire fixture; no partial image vector |
| N42 adapter repair | Local 3/3 plus remote portable success; old missing canonical_source_id/bind_null/links.id repaired, not skipped |
| Existing regression and package | 47 exact native groups, 51 HTTP checks, prior memory/MCP/hooks/context and both PowerShell suites; same-source packaging succeeded |
| Source and delivered-byte integrity | 644 archived source files matched the local candidate; 86 downloaded-artifact checks passed |

The original N46C differential suite still passed 139107 assertions, including
looped properties, after synthetic queries explicitly named their seeded model.
No historical assertion was removed. Nine evidence-gate tests reject obsolete
logs lacking the new 47th group. Real PostgreSQL DSN tests explicitly remain
SKIP-PG; a passing enclosing group is not PostgreSQL integration acceptance.

## Supplemental checks and actual limitations

Clang AddressSanitizer/UndefinedBehaviorSanitizer instrumented the local linked
C++ and bundled SQLite C. The 65-check embedding suite passed. A separate parser
probe passed exact maximum-count/width/total-element boundaries and 20000
deterministic mutations (21454 assertions), without sanitizer diagnostics.
These are Linux checks, not Windows sanitizer or full-application coverage.

The local full historical regression target did not compile because existing
Windows-specific tests use `_putenv_s` on Linux. This was retained as NOT PASS;
the successful Windows full suite, rather than a fake portable substitution,
provides native regression evidence. The baseline N42 portable failure in run
34662238488 was also retained. No failed N46D native run was retried or hidden.

## Delivery and review status

Original CI inner ZIP: 1837987 bytes, SHA-256
`e057f6e4eda2306357643b963f2d8b9a62e0748b14a8b71bfd46de29607c7deb`.
EXE: 3806208 bytes, PE32+ AMD64, no embedded Authenticode signature; SHA-256
`d3c8ff4b565117e785c933b35cb6795cee4ee580f0d696c575ca467480fcce5f`.
The ZIP and scripts were not reconstructed; exact CI bytes are retained.
Windows scripts differ from Git blobs only by the verified LF-to-CRLF checkout.
See [machine summary](n46d-evidence/SUMMARY.json) for artifact IDs and log hashes.

No runtime defect was observed in the scoped tests. This does not substitute for
the independent review gate. Model label plus width is not endpoint/provider/
weight attestation. Raw low-level C++ vector_search still has its documented
unfiltered compatibility mode; no CLI/MCP bypass was introduced. Model alias
mismatches now fail explicitly. Legacy vectors are not relabelled or deleted.

No schema migration, new MCP operation, automatic external-processing permission,
paid model call, logged-in Win11 Agent acceptance, PG parity or signed release.
Review approval and any merge remain separate from these automated results.
