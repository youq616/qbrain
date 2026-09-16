# N47I outcome review — unambiguous bounded public JSON

Verdict: PASS for this scoped implementation after the actual gates below.
Reviewer: ChatGPT, separate owner-authorized engineering self-review. Not an
independent subagent, third-party audit or a universal defect-freedom guarantee.

Baseline: f4a07e71df831843989996d8d537e036364591bc.
Tested/reviewed product: 093088165315b8bc874bfd9ac934efbd4d101f87.
Source tree: b80eeb785a9981bf761ebd3732483285d46146d6.
The 827 files in the original source artifact reconstruct that exact tree. The
17 implementation/test/build paths match the locally built source byte for byte.
Outcome documentation and supplemental scripts are not added to product targets;
they do not alter the tested runtime, original tests, workflows or package bytes.

## Actual defect and narrow policy

The original binary accepted duplicate session/role and fact predicate fields,
and selected the final duplicated MCP id. This was reproduced through real CLI
and MCP requests in a synthetic brain, not inferred only from parser documentation.
It is ambiguous-input/data-integrity behavior, not an asserted authentication bypass.
RFC8259 recommends unique object names; rejection is an explicit application policy,
not a claim that every duplicate object violates JSON's grammatical production.

The shared parser checks full decoded key names in a separate set for each object.
It raises an exception rather than returning false from the callback, which could
silently discard data. Escaped-equivalent and nested duplicates are rejected;
sibling objects may reuse names, and case/Unicode-normalization distinctions remain.
Raw NUL is rejected before the vendored parser can treat it as end-of-input.
Escaped NUL in a valid JSON string is not confused with a raw byte or truncated key.

## Approved-plan acceptance

| Requirement | Review and actual execution | Outcome |
| --- | --- | --- |
| Reject before a map silently overwrites | Top-level, nested, escaped, same-value and NUL-containing decoded key cases | PASS |
| Preserve valid unique-key semantics | Sibling objects/arrays, Unicode, quoted JSON text, exact byte/depth limits | PASS within documented bounds |
| Ordinary capture/fact inputs | Stable memory_duplicate_key/fact_duplicate_key, no optional module, event or fact/revision write on rejection | PASS |
| Preserve batch contract | Historical fact_batch_duplicate_key, size/depth errors and valid batch preview retained | PASS |
| MCP reject before dispatch | Fixed -32700/id=null, including malformed notification; no chosen duplicate id; valid next request still works | PASS |
| Hook rejection before state changes | Invalid events return existing benign response before brain open/lock/trace/capture; valid control records actual session/event | PASS in synthetic process fixtures |
| No authorization expansion | Source allow-list, write-default-deny and six memory-profile names unchanged | PASS |
| Bounded public parsing | Per-route raw byte/depth limits, invalid UTF8/surrogate/syntax/trailing documents and raw NUL fail | PASS |
| Same-source native acceptance | Windows 57 registered groups, Server2022 unit, portable, sanitizer and final packaging | PASS |

Memory/fact payload event depth is8; MCP and Hook event depth is32. Raw byte caps
are16KiB ordinary fact,256KiB capture/Hook,8KiB batch and16MiB MCP body. Deep otherwise
unique inputs outside the new documented bounds intentionally stop working. Valid
input semantics *within* those bounds are preserved. No existing stored transcript,
configuration parser, schema, installer switch, provider consent or memory evidence
is rewritten. CLI/serve may still perform their existing core startup before the
inner operation: rejection is not a claim that all process startup is write-free.
Hook parsing is separately checked before its runtime state path is assigned.

## Separate outcome-pass checking

The parser's object stack and exception lifetimes were inspected separately from
implementation: state is call-local, sibling and array nesting preserves scope,
throws unwind all temporary key sets, no callback can discard a value and return
partial success. No key/value is included in the new errors. Route checks were
reviewed for outer-versus-inner parsing and valid write/source permission behavior.

An independent Python decoder retaining object pairs supplied expected results for
7,781 raw JSON inputs; it did not use the new C++ parser as its own oracle. Corpus
includes generated unique/duplicate/nested/sibling structures, Unicode spellings,
malformed UTF8/surrogates, numeric boundaries, depth and byte limits. All observations
matched:4,028 accepted and3,753 rejected. Actual parser process exit0 and empty
stderr. Scope is finite differential testing, not all-input correctness.

An additional48-input wide/deep and recovery set also passed, including objects
with32,768 unique keys and deliberately over-depth array input containing200,000
nesting markers. Over-depth inputs were rejected at the configured boundary, not
fully descended. A valid control after each row succeeded in the same process.
This is finite robustness checking, not a latency or memory-resource guarantee.

Two temporary deliberately broken helpers were compiled and exercised against the
same corpus. Removing duplicate rejection produced3,630 mismatches; removing raw
NUL rejection produced1. Both oracle invocations exited1. Candidate source remained
unchanged. The exact oracle source/report and mutation summary are archived.

The frozen final process script was also rerun against the old baseline executable:
it exited1 on the first duplicate-capture case, where the old binary returned0
instead of the required1. This final-script run is separately retained from an
earlier precursor-script run, not misattributed to the final script hash.

Local production and new11-scenario/95-assertion unit checks passed; all16 new and
retained process suites exited0. New raw CLI/MCP/Hook suite:54 named checks/39 commands,
23 expected exit0 and16 expected negative exit1. Twelve report/registry suites were
re-executed during outcome review:157 tests, all passed. Archive-only local wrappers
correctly keep source_commit=null; source identity is separately tied to the exact
reconstructed archive tree rather than fabricated Git metadata.

## Failures and limits retained

Initial new-test compilation failed on incorrect C++ test types; those fixture
types were corrected before the candidate. A new Hook positive control initially
expected capture_status=captured, but the established contract is archived. The
fixture was corrected and augmented with real session/event checks, not a runtime
change or deletion of the positive test. All final process checks passed.

An additional attempt to compile the complete aggregate qbrain_tests under Linux
failed in unchanged historical tests/test_n19.cpp and tests/test_n20.cpp, which
use Windows-specific _putenv_s/gmtime_s. That attempt returned1 and the full local
aggregate did NOT run. No Linux compatibility shim or disabled test was added to
hide it. The complete native Windows aggregate is separately executed and verified
below. The local scoped production/unit/process and CI portable/sanitizer results
remain separate from this unsupported aggregate attempt.

No scoped unresolved P0/P1 found. This does not certify all parser entry points,
HTTP framing, NDJSON buffering performance, arbitrary memory usage or whole-application
security. Per-input bounds are not hard real-time, total-memory or database-I/O
bounds. Other configuration/stored-data parsing and existing source policies remain
outside this change. Synthetic Claude/Codex event formats are not newly authenticated
client sessions. Existing Codex gateway authentication is not touched.

## Native execution and original artifact verification

Development35134498540 and N4235134498732 completed all required jobs on09308816.
Windows full aggregate has57 exact registered groups; real PG DSN cases remain
explicit SKIP-PG, not passed PG integration. New strict JSON unit11/95 passed on
Server2025,Server2022,portable and Linux ASan+UBSan. New process54/39 passed on
Windows,portable and sanitizer; expected negative exits are not relabelled all-zero.
Sanitizer CI instruments SQLite C and application C++ using Clang18.1.3, with
halt-on-error enabled, and retains prior batch/candidate/recall coverage.

All previous fact, conflict, recall, Hook, promotion, lifecycle, batch and candidate
unit/process gates remain. Both Windows HTTP wire suites have81 checks and fixed
cancellation/cache-shutdown schedules. CJK,embedding,queue,memory,context and both
PowerShell versions retain their earlier checks and explicit consent gates.

Six original artifacts were downloaded and externally SHA256/size-checked before
interpretation. The full source tree, inventory, original report equality, complete
unit scenario sets/assertion counts, process names/command schedules/negative exits,
source/script/EXE identity, installer and inherited transport evidence passed
379 additional readback checks. The checker runs no product binary.
Diagnostic probe executables were not downloaded separately; their hashes are
bound to fixed original reports and the original package job's actual probe checks.

Original inner ZIP:2055158 bytes; SHA256
7f99a7e8781047e2dd5a9f482b522842cb6c79170e81c313084917cd657ba598.
Original Windows EXE:4027904 bytes; SHA256
5576c4ecbcf6a512f914cd23c0dc1ebc6a05b1ce7bd5da31fcffe0d5fa573a92.
These are original tested CI bytes, not rebuilt/repacked delivery artifacts. Still
unsigned. Integration and fixed reviewed-candidate preview publication may proceed;
no general unreviewed auto-publication, old Release overwrite or new local-agent
task is authorized by these tests. This hardening node is not semantic consolidation,
automatic aging, usage counters or whole-project completion.

References consulted:
https://www.rfc-editor.org/rfc/rfc8259#section-4
https://json.nlohmann.me/features/parsing/parser_callbacks/
https://www.jsonrpc.org/specification
