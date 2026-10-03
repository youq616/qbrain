# N49D — directory-scoped MCP search

**Status**: approved / implementation in progress
**Depends on**: accepted N49C integration, actual commit `cfe1ef58e244b51092c2248804b663b6c28913d7`, tree `75b69ad389630e51528ddb5536a27255203470df`
**Plan audit**: PASS (`N49D-PLAN-AUDIT.md`); original MCP contract and the version 2 native build-phase amendment are approved
**Outcome audit**: pending; native candidate qualification and a separate independent outcome review are required

## User value and scope

An MCP client can use the existing `search` tool to search one directory recursively instead of searching its entire authorized source. Both the full and six-tool memory profiles advertise the same optional `uri` argument. The accepted CLI directory-search implementation is reused unchanged.

This node adds one positive client capability, not a new tool. It does not establish real-account/client consumption, model quality, cost savings, PostgreSQL directory support, package readiness, or overall project completion. All fixtures use disposable synthetic SQLite and built-in or loopback provider mocks.

## Provenance and repository instructions

The remote `integration/n49c-client-retrieval` ref and Git commit API were verified on 2026-10-02 and both identify the actual commit and tree above. This node starts at that exact accepted commit.

`AGENTS.md`, node process/template, master plan, completion roadmap, current status, N48Z CLI plan, build instructions, and the applicable code/build registrations were read. No repository `.agents/skills` directory is present. The owner overrides permit a real separate-agent plan/outcome review instead of mandatory external Claude Code review; the remaining gates stay in force.

The prior N49C qualification remains historical evidence for its exact candidate. Neither its qualifier nor its workflow is edited or represented as passing on this new tree. N49D has its own bounded source-delta gate and qualification.

## Exact contract

1. `search` gains optional string `uri`; omission preserves the current handler path, output shape, source selection, tool counts, ranking, and write policy.
2. Effective source is selected after the unchanged MCP argument conversion: explicit string values remain strings, null is omitted and permits ambient/default fallback, Booleans become `1`/`0`, integers become decimal strings, and arrays/objects become JSON text that source canonicalization rejects. A converted explicit `source_id` wins; otherwise present `QBRAIN_SOURCE` is used, otherwise `default`. Explicit empty or present-empty ambient source is invalid, not a default request. Existing ASCII case canonicalization remains intact; a URI prefix must itself use literal canonical spelling. The existing `resolve_source` and `remote_source_allowed` functions remain byte-for-byte unchanged and run before URI parsing/search or provider work. This node does not add a source-argument type restriction.
3. A URI only narrows that resolved, existing, authorized source. It never selects a source. Before calling the existing parser, require the URI's literal source prefix to match `qbrain://<resolved-source>/`. This avoids looking up a different source through the parser. A mismatch is a structured `invalid_argument` error with field `uri` and no input echo, hits, or broad fallback.
4. Present `uri` must be a JSON string. Null, number, Boolean, array, and object are rejected before the generic MCP argument conversion. This validation is specific to `search.uri`; it does not tighten unrelated legacy search arguments or other tools.
5. For well-formed JSON, a present nonstring `uri` receives a bounded tool argument error on `uri` before generic conversion. For valid decoded string values, empty, malformed, non-directory, overlong, noncanonical, traversal, encoded-separator or invalid-byte URI receives a bounded URI rejection, subject to the existing query/source-error precedence. Direct-handler invalid UTF-8 bytes are tested at that layer. Malformed wire JSON, UTF-8, Unicode escapes, or raw NUL retains the existing JSON-RPC parse error `-32700` with null ID and no dispatch/provider call; do not alter the general JSON parser. Valid escaped `\u0000` decodes into a URI string and is rejected at the URI layer. A valid directory URI uses `resources`, `skills`, or `memories`, ends in `/`, and preserves the existing parser's exact UTF-8 prefix behavior. A valid empty-result scope succeeds with the existing empty-result shape.
6. New URI validation and existing source authorization finish before embedding/provider work. Authorized scoped calls use the existing source-bound query embedding path, then unchanged `directory_search`. Transfer only the existing `DirectorySearchOpts` fields: `limit`, `rrf_k`, `mode`, `rerank`, `rerank_llm`, and `config`. Existing `no_vector` controls whether a query embedding pointer is supplied; there is no new options member or header change. No new ranking or caching behavior is introduced.
7. Source, namespace, exact directory-prefix, and deleted-page filtering precede lexical/vector ranking. Siblings such as `docs-neighbor/`, case variants, other sources, and other namespaces cannot enter results. The accepted directory implementation, CLI path, and their tests remain unchanged.
8. Existing result fields and text/structured MCP response formatting are retained. Memory profile remains exactly six tools; full-profile operation names/count remain unchanged. Default-deny writes and loopback HTTP authentication remain unchanged.

## Frozen exclusions

N49B/PR63, PR61-specific machinery, PostgreSQL directory/cache/context/storage work, and historical frozen probes are outside this node. Do not fetch, inspect, reconstruct, alter, recover, or build an alternative route for those excluded operations. Do not import their historical probes into new tests. If implementation or a requested gate would require that scope, stop and report it. Generic inherited source identities may be compared without opening their contents. No migrations, new tools, registry policy changes, new provider integration, main merge, deployment, release asset replacement, real account/data, or paid provider calls.

## Exact file allowlist

Production edits:

- `src/qbrain/ops/handlers.cpp`: add the existing directory-search header and change only the `search` registration/body; preserve `think` and all other handlers/helpers
- `src/qbrain/mcp/server.cpp`: add only a narrow `search.uri` string check before generic argument conversion; preserve profile, ambient-source, response, and transport logic

New tests/build/qualification files:

- `tests/test_mcp_directory_search.cpp`: ordinary SQLite handler/schema/authorization functional cases
- `.ci/mcp_directory_search_targets.cmake`: register the new test and the unchanged directory test; no root build-file changes
- `.ci/test_mcp_directory_search.py`: actual CLI, stdio, and authenticated loopback HTTP process checks with disposable data, raw requests/responses, bounded process timeouts, and explicit process cleanup
- `.ci/check_n49d_sources.py`: exact base/tree and file-delta binding; production changes restricted to the two approved regions; the two reviewed build wrappers are pinned by exact canonical blob identity; all other inherited file identities unchanged
- `.ci/test_n49d_source_contract.py`: finite source/recorder/package/consumer controls described below, using newly created generic dummy fixtures only
- `.ci/run_n49d_qualification.py`: owns the small fixed-stage command/evidence recorder, stricter packaging wrapper, and bounded downloaded-artifact consumer; explicit failure/timeout status, raw stdout/stderr, candidate/binary hashes, and final bounded manifest; reuse only suitable unchanged generic packaging/tree-validation primitives, not the N49C qualification framework
- `.github/workflows/n49d-mcp-directory-search.yml`: candidate-pinned Linux CMake, Windows CMake, Windows direct-MSVC, and Linux ASan/UBSan jobs

Documentation/evidence edits:

- `docs/nodes/N49D-PLAN.md`
- `docs/nodes/N49D-PLAN-AUDIT.md`
- `docs/nodes/N49D-HARD-AUDIT.md`
- `docs/integration/MCP-DIRECTORY-SEARCH.md`
- `docs/OPS-PARITY-LEDGER.md`: only the existing `search` row's bounded capability/evidence note; no operation-count or unrelated status changes
- `docs/nodes/n49d-evidence/RESULT.json`: compact truthful state and links/identities for actual qualification evidence
- `docs/nodes/n49d-evidence/SOURCE-MANIFEST.json`: compact approved base and changed-file binding

The version 2 amendment additionally permits `scripts/build-cl.ps1` for exact-zero working-directory/tool guards and `scripts/build-tests-cl.ps1` for the reviewed build/run phase interface and guards. These are modified inherited files. The cumulative accepted-base delta is eighteen paths. No `CMakeLists.txt`, overlay, directory-search implementation/header, CLI source, inherited test, old workflow/qualifier or old evidence change is included. Any other path needs a reviewed amendment.

## Falsifiable acceptance and tests

### Native C++ functional tests

- In-memory synthetic default/allowed/denied sources and ordinary page fixtures cover resources/skills/memories, namespace root, nested descendants, Unicode directory/query, siblings, case variants, deleted pages, and empty results
- Direct handler and MCP dispatch exercise the existing tool, present/omitted URI, malformed/empty values, source mismatch, missing source, denied source, valid allowed nondefault source, and explicit source overriding ambient source
- Paired present/omitted-URI tests preserve the existing source conversion for null, empty, Boolean/integer and uppercase explicit sources and empty ambient source. Separate malformed-envelope tests preserve `-32700` while decoded malformed URI/nonstring errors remain tool errors. Source/query-error precedence is asserted instead of overriding it
- A URI naming another source is rejected rather than selecting it; authorization failure remains the existing source error and cannot fall back
- Full and memory tools/list schemas advertise optional string URI; tool-name sets remain equal to base sets, with memory exactly six
- Omitted URI yields the same result serialization and source restrictions as the pre-change hybrid handler; default-deny write checks still reject
- The unchanged directory test proves candidate-before-ranking filtering, including its existing crowd and vector cases; new MCP tests exercise mock query-vector integration rather than duplicating ranking implementation. No new cache observations or cache-internal test seams are introduced

### Actual process tests

- Start actual stdio servers on Linux and Windows and actual loopback HTTP servers on Windows for full and memory profiles using a disposable SQLite root; HTTP uses synthetic local token authentication and rejects missing/wrong token. The existing non-Windows HTTP server is a stub returning 2, so Linux receives only in-process remote-dispatch checks, never an actual-HTTP PASS claim
- Compare ordered full result objects from CLI `search --uri` and MCP search for the same effective authorized source, namespace, query, mode, and no-vector setting; retain raw process output
- Exercise default source, environment source, explicit override, nondefault allowed/denied source, URI-only attempted source selection, malformed/empty/null/wrong-type URI, valid no-results URI, Unicode/nested/sibling/deleted behavior, and unchanged no-URI search
- Exercise lexical and vector-enabled retrieval with synthetic provider mocks and preloaded matching embeddings; assert scoped result membership and absence of unrelated namespace/source pages
- On both Windows products, an isolated loopback embedding-provider fixture uses synthetic credentials, unique rejected queries, zero captured requests for those rejections, and mandatory fresh valid-query controls that reach the same fixture. Disable the built-in mock only for this isolated case. Linux retains functional mock-vector/source/wire checks without a provider-network/count claim
- Run process tests under normal Python and `python -O`; assertions required for correctness use explicit checks, not removable Python `assert`
- Retain exact argv, exit status, request/response bytes, stdout/stderr and their hashes; failure and timeout remain failed/partial evidence, never successful missing stages

### Required candidate qualification

1. Fresh Linux and Windows CMake builds of production `qbrain` and these exact selected targets: `qbrain_mcp_directory_search_tests`, `qbrain_directory_search_tests`, `qbrain_memory_tests`, `qbrain_context_tests`, `qbrain_http_tests`, `qbrain_retrieval_tests`, `qbrain_embedding_tests`, `qbrain_embedding_queue_tests`, `qbrain_cjk_tests`, `qbrain_recall_tests`, `qbrain_strict_json_tests`, and `qbrain_multiterm_tests`. The corresponding required CTest names are `qbrain_mcp_directory_search_unit`, `qbrain_directory_search_unit`, `qbrain_memory_unit`, `qbrain_context_unit`, `qbrain_http_input_unit`, `qbrain_retrieval_unit`, `qbrain_embedding_unit`, `qbrain_embedding_queue_unit`, `qbrain_cjk_unit`, `qbrain_recall_unit`, `qbrain_strict_json_unit`, and `qbrain_multiterm_unit`. The test inventory and run must match all twelve names with zero unexpected skips. Windows additionally builds `qbrain_http_probe` for its native WinHTTP process regression.
2. Windows CMake canonical `qbrain_tests` suite and fresh Windows direct-MSVC production build followed by the versioned BuildOnly and strict RunOnly phases below; verify all sixty registered canonical groups from the actual strict-run log using the unchanged ordinary native-log parser. No historical PASS substitutes for these current runs.
3. Run `.ci/test_mcp_directory_search.py`, `.ci/test_directory_search.py`, `.ci/test_context_process.py`, `.ci/test_hooks.py`, `.ci/test_memory_cycle.py`, and `.ci/test_named_arguments.py` in normal and optimized Python on each fresh Linux CMake, Windows CMake, and Windows direct-MSVC candidate executable. The new process driver requires stdio on both platforms and authenticated loopback HTTP on Windows; Linux HTTP non-applicability is explicit in the report and cannot satisfy the Windows requirement. Additionally run unchanged `.ci/test_http_transport.py --probe <qbrain_http_probe> --report <path>` in both Python modes on Windows CMake; this existing WinHTTP gate explicitly rejects Linux. Do not invoke historical frozen specialized probes.
4. Linux ASan/UBSan fresh builds of the new functional test and unchanged directory test; nonzero exits or sanitizer diagnostics fail the stage.
5. New finite allowlist/source-binding self-tests. Candidate/base tree IDs, complete Git tree inventory, changed-source bytes/hashes, exact commands/exits, binary hashes, raw test output, and leaf manifest bind the evidence to the actual candidate. Full old source/evidence archives are not copied into the new artifacts.
6. Independent outcome reviewer checks the approved contract, exact diff, source identity, selected-test completeness, raw process results, all four current native jobs, and final artifacts. Record actual reviewer identity, commands, findings, and limitations. Only that reviewed result can support `done`.

### Command contract

The qualification runner owns these literal stage definitions; paths are substituted from its validated source/build/output arguments, not arbitrary shell fragments. CMake uses `-DQBRAIN_WITH_PG=OFF` and `-DCMAKE_PROJECT_qbrain_INCLUDE=<source>/.ci/mcp_directory_search_targets.cmake`. Linux CMake uses Debug with `-DCMAKE_CXX_FLAGS_DEBUG=-O0 -g0` and `-DCMAKE_C_FLAGS_DEBUG=-O0 -g0`, retaining runtime assertions while avoiding duplicate debug-symbol storage. Windows uses native Debug. Both build `qbrain` and the twelve targets named above using `cmake --build <build> --config Debug --target <exact-list> --parallel 2`. The CTest invocation uses `ctest --test-dir <build> -C Debug -R <anchored-exact-name-union> --output-on-failure`; `ctest --show-only=json-v1` provides the expected inventory to compare before running.

Windows CMake separately builds `qbrain_tests qbrain_http_probe`, executes `qbrain_tests.exe`, and calls the unchanged `.ci/validate_native_log.py` ordinary `verified_groups` function with `expected_count=60` against `tests/test_main.cpp` and the actual output. Windows direct-MSVC runs `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-cl.ps1`, then the exact BuildOnly and strict RunOnly commands below. Only the strict RunOnly stdout supplies its canonical sixty-group proof. The wrappers retain their existing default combined behavior, with the reviewed exact-zero failure guards.

For each `python` and `python -O` mode, run the six process drivers listed in item 3 with `--binary <exact-built-qbrain>`; use `--output <fresh-path>` for both directory drivers, `--report <fresh-path>` for context/named-argument drivers, and raw stdout/stderr capture for every driver. Windows CMake additionally invokes the named WinHTTP probe command. The new driver reports all actual request/response records and the Windows-required HTTP stage explicitly. No provider credentials or inherited `QBRAIN*`/`PG*` configuration enters the test environment.

The sanitizer job configures Clang Debug, PG off, the same overlay, `-DCMAKE_C_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer`, `-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer`, `-DCMAKE_C_FLAGS_DEBUG=-O1 -g0`, `-DCMAKE_CXX_FLAGS_DEBUG=-O1 -g0`, and `-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined` (each full cache assignment is one argv element). Both Debug-specific flag variables are overridden explicitly; an inherited later `-g` must not re-enable debug symbols. Build and run only `qbrain_mcp_directory_search_tests` and `qbrain_directory_search_tests`. Retain effective compile/link commands, verify `NDEBUG` is absent and ASan/UBSan instrumentation is present, and record the exact runtime options `ASAN_OPTIONS=detect_leaks=1:halt_on_error=1` and `UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1`. Both raw stderr streams must be empty and exits zero. All jobs run `.ci/test_n49d_source_contract.py` under normal and optimized Python and run `.ci/check_n49d_sources.py` before and after native execution. A nonzero/timeout/missing required stage makes the node's result failed or incomplete.

### Finite evidence-wrapper controls

`.ci/run_n49d_qualification.py` is the sole new recorder/package/consumer implementation path. Keep it proportional: fixed stage definitions and bounded I/O around the unchanged generic archive/tree primitives, not a replacement framework. Derive exact command and requested-report inventories from a fixed per-job contract; require requested/actual report-set equality and validate every mandatory semantic report. A nonempty command or self-declared report map is insufficient. The recorder requires each named stage exactly once, explicit candidate/tree and pre/post binary/source identities, both raw streams, a result report, and an exit classification. Child failure, timeout, missing/duplicate stage, missing file, or changed identity cannot produce overall success. Preserve partial bounded diagnostics on failure. Set finite stage timeouts and stream budgets (configure 180 seconds, build 1,800 seconds, native/process stage 600 seconds, self-tests 120 seconds; at most 8 MiB per stdout/stderr stream). Reaching a timeout/output budget is a failure, not successful truncation.

The recorder and process driver share one bounded owned-child implementation. One success deadline covers launch, leader and descendant exit, pipe EOF, reader completion, cleanup and stable final output hashing. Unexpected surviving descendants make strict-v1 finite commands fail; intentional HTTP fixture shutdown remains separate. Only the five fixed Windows build/configuration pairs below can use trusted-build-v1, requiring real root-zero completion and the complete owned-job/readiness proof. A prior failure cannot be relabeled under that policy. A small cleanup grace is allowed only after failure and cannot turn timeout into PASS. Windows uses suspended launch into a private non-inheritable kill-on-close Job Object before resume, with no breakaway or unowned fallback. Linux is restricted to one active owner and no unmanaged/pre-existing child ambiguity in that helper process; only attributable descendants/adoptees may be signaled through pidfds or guaranteed-unreaped owned identities. No process-table sweep, arbitrary-child reaping, new supervisor command, host-wide setting, service or production behavior is added; prior subreaper state is restored only after owned cleanup. Attribution/API failure remains failed or incomplete.

If the Linux child-list pseudo-file is absent with `ENOENT` during self-process preflight, a bounded numeric `/proc/<pid>/stat` read adapter may identify PPID/ancestry relationships under the same exclusive-owner contract. Bound record bytes, inventory count and read time; verify PID/start-time and ancestry around pidfd acquisition. Permission denial or unknown errors do not select this alternative. Do not use global baseline differences, export unrelated process metadata, signal unrelated PIDs, or reap arbitrary children. The adapter changes observation only and does not weaken ownership or cleanup rules.

In both normal and optimized Python, `.ci/test_n49d_source_contract.py` must exercise the N49D wrappers and their failing return status for these exact negative controls, plus a small valid control for each wrapper:

- Wrong base/tree, changed inherited file, extra/deleted file, and edits outside either approved production region
- A nonzero child, a short bounded timeout child, missing/duplicate required stage, and missing raw stdout/stderr or result report
- Genuine recorder and process-driver controls for parent exit with inherited or redirected pipes, detached/silent descendants, delayed output, drain timeout, overflow, ownership API/cleanup failures, intentional HTTP stop, concurrent/ambiguous owner rejection, and an unrelated surviving sentinel; no owned writer remains and final hashes stay stable. Platform-mocked failures do not replace native Windows controls
- Swapped candidate or binary identity and source/binary mutation after capture
- N49D manifest, member-count, raw-size, compressed-size and consumer-staging caps; missing/extra outer member; wrong part or manifest hash; wrong job, run attempt, or candidate identity
- A requested driver report genuinely deleted with its metadata map also omitted, wrong command records, and missing fixed-job semantic reports; valid and negative calls through the actual package orchestration using only a narrow injected generic-packager fixture seam, never modified production packager guards

Use new generic dummy files/short subprocesses and small injectable test limits instead of allocating production-sized boundary files. These controls do not execute/import historical source/phase/probe qualification machinery; named unchanged generic packaging/hash/archive/tree validators are the only reused primitives. A source-only self-test result does not satisfy recorder/package/consumer controls. Old specialized runs remain historical; final acceptance stays explicitly limited to this node's listed obligations.

The workflow is new and candidate-pinned. Automatic activation is restricted to a push on the new `feature/n49d-mcp-directory-search` branch, subject to the separate source-review and publication gate. This allows native CI without merging a new dispatch-only workflow into the default branch. Its new source guard permits only the reviewed two production deltas and listed new support/docs paths. It does not modify, relax, import, or assert a new PASS for the old N49C guard. The prior guard and workflow remain exact inherited Git blobs.

## Capacity and local validation plan

Local validation is deliberately capacity-bounded. Reuse immutable accepted dependency bytes without downloading duplicates; any shared or hard-linked dependency must never be edited. Before and after each local build, verify every dependency file's Git blob and SHA256 against the accepted base and verify any shared link locations still have identical bytes; store the dependency manifest. Any mismatch stops the task. No duplicate full history/archive copy, cache deletion, or prior-evidence deletion is permitted.

Local validation will use at most one fresh compact Debug (`-O0 -g0`, assertions retained, bounded parallelism) build directory for `qbrain`, the new functional test, and the unchanged directory test, only if a preflight confirms that estimated objects, binaries, temporary fixtures, and raw evidence fit while retaining at least 150 MiB free. Cap local build/evidence growth at 80 MiB; record disk before/after and stop if capacity is unsafe. Existing Debug executables are not accepted as candidate build evidence. No local native-Windows pass will be claimed. If the compact local build cannot fit, complete static/source/driver checks and report native execution as pending; required fresh native qualification runs in CI after the independent freeze/publication gate.

### Bounded artifacts and supported materialization

Each job's evidence contains raw output, stage reports, dependency/source identities, complete tree inventory, changed-source bytes, and the exact tested production executable (CMake/direct jobs) or two tested focused executables (sanitizer job); store hashes of all other executed binaries without duplicating their bytes. No PDB, object/archive cache, whole repository, old evidence, database, credentials, or inherited source archive is uploaded. Limit each job to 160 MiB raw evidence, 4,096 regular files, a 512 KiB manifest, and a final compressed archive of at most 20 MiB. Retain exact source/binary bytes; do not strip or rewrite a binary after its identity was recorded. Record actual required-binary and package sizes before upload. The 20 MiB limit is a measured fail-closed gate, not an expected-fit guarantee; an overrun stops for a reviewed bounded adjustment without omitting binaries/evidence, silently splitting, or switching materialization routes.

| Capacity input | Historical observation or current bound |
| --- | --- |
| Accepted Linux production executable | Historical 48,989,144 raw / 15,420,423 compressed bytes; not an N49D measurement |
| Accepted Windows CMake / direct-MSVC executables | Historical compressed 2,504,974 / 2,317,857 bytes |
| Accepted sanitized directory + client-retrieval executables | Historical compressed 11,022,327 + 11,258,700 = 22,281,027 bytes, already above 20 MiB; default Debug is not a valid fit assumption |
| N49D no-debug-symbol binaries | Unmeasured before implementation; effective g0/O1 may reduce size but the actual cap must still pass |
| Four official evidence downloads | Hard bound below 84 MiB, including <=2 MiB aggregate manifests and ZIP framing |
| Consumer reconstruction + selected text | At most 20 MiB reconstruction plus 6 MiB retained review text, inside the 110 MiB aggregate staging cap |
| Local compact build/evidence | Hard 80 MiB cap with static-only fallback, plus at least 150 MiB free reserve; no fit guarantee |

Use unchanged `package_evidence`, its bounded writer, and its archive/leaf validation primitives from `.ci/check_n49c_sources.py` only as a packaging format implementation, with independently supplied N49D commit/tree/run/attempt/job identity. Do not call or modify its source/ancestry/phase qualifier. Add stricter N49D pre/post caps so exactly one `20 MiB` or smaller `part00` is uploaded with its at-most-512-KiB manifest using artifact compression level zero. This yields an outer ZIP below 21 MiB, comfortably within the supported 32 MiB file materializer. Preserve the inherited container schema as a transport-format identifier, never a claim of N49C qualification. Use unchanged `.ci/check_source_archive.py` `tree_from_manifest` for complete-tree reconstruction without importing full-source archives.

The workflow uploads one required evidence artifact per job and an optional failure/packaging-diagnostic artifact capped at 256 KiB. Failure diagnostics preserve bounded exact raw stream tails, full available sizes/hashes, explicit truncation/failure classification, and result/report metadata; they never stand in for a complete successful artifact. A cap overrun fails packaging and preserves bounded CI diagnostics; do not omit required successful evidence, split into unbounded artifacts, or label a missing artifact successful. Expected upper bound is four evidence artifacts totaling under 84 MiB plus at most 1 MiB diagnostics. The job/run/attempt/commit identity and GitHub artifact digest are read independently before downloading.

Download official GitHub Actions artifacts only through a supported bounded file-transfer route with a 32 MiB maximum. Check the independent GitHub digest, exact outer members, safe regular-file types, bounded sizes, and manifest/part hashes. A small N49D consumer reconstructs at most 20 MiB with a preflight capacity check, then reuses the unchanged streaming archive/leaf validator; it does not lower or bypass old N49C materializer guards, which remain applicable to N49C's larger artifact contract. Do not extract all native binaries; stream-hash archive members and materialize only bounded text/raw records required for review. Retain downloaded evidence and reports, cap all four-job review materialization plus reconstruction at 110 MiB, and keep the 150 MiB free reserve. Any insufficient capacity is a blocker to report, never a reason to delete old cache/evidence or use an unsupported download route.

The consumer first stream-hashes every member and validates all mandatory semantic evidence directly from the retained archive. Its enumerated materialized subset is: `qualification.json`; the complete tree inventory, dependency record and changed-source bytes; every required stage's `result.json`; every fixed-contract requested report except the already-compared duplicate `reports/source-after.json`; and stdout/stderr for `selftest-*`, `sanitize-*`, `hooks-*`, `memory_cycle-*`, `ctest-run`, `canonical-run`, `canonical-groups`, `direct-tests-build` and `direct-tests-run` where applicable, plus every required version 2 readiness/object/context/pair report. Unselected source-after, build and process raw records remain intact in the official archive and are still validated. No binary is extracted. Selection completeness, unselected-member corruption and cumulative text/staging limits have finite controls; the aggregate 6 MiB retained-text cap remains a measured fail-closed gate.

## Review, publication, rollback, and parallelism

The plan must receive a real independent PASS before its status changes to approved and any implementation begins. After approval, the two shared production files have one owner; an independent worker may build tests/docs on disjoint new paths. Freeze the candidate and obtain a separate code/evidence review before any publication request.

After separate authorization, create an unreferenced exact candidate, verify its actual parent, complete tree and all changed blobs, then obtain authorization for a non-forced update of the dedicated development branch and CI. The accepted integration branch and main branch remain unchanged. PR creation, merge and deployment require their own authorization. Public descriptions contain only public feature/source/CI facts.

Freeze source and documentation together. In the exact candidate, the plan remains approved/in progress, `N49D-HARD-AUDIT.md` and `RESULT.json` explicitly state native qualification/outcome acceptance pending, and the ledger/user guide identify a candidate feature with pending native acceptance. Final acceptance is recorded in a separate immutable independent outcome report tied to the exact candidate commit/tree and CI artifacts. Do not make a post-test status-only commit that changes the qualified candidate identity. Any later in-repository closeout is a separately authorized documentation change and cannot be silently substituted for the native-tested tree.

Rollback is an ordinary revert of this node's additive schema/dispatch change and new tests/docs. There is no data/schema migration or persisted-format change. Removing `uri` support returns clients to the unchanged pre-node search behavior. Native failures or independent blocking findings keep the node open; repairs require fresh affected tests and independent re-review.

## Ledger and security

The existing `search` operation gains a narrowly evidenced MCP directory capability note only after its actual qualification. No new ledger row or count is added. Source authorization is checked before URI parsing/provider work; URI data is never authorization. Errors are bounded and do not echo user input. Default write denial, loopback binding, transport authentication, and other tool contracts are preserved.


## Version 2 Windows build-phase contract

This amendment changes native qualification, while preserving the MCP feature contract. For five explicitly bound Windows job/stage pairs, a reviewed tool root's actual zero exit declares its requested compiler/configuration work complete; the same owned job may then be deliberately terminated before finalization. This is an explicit trusted-tool assumption. A process basename or stable file hash cannot establish that an auxiliary process is harmless, and prior failed runs retain their original outcomes.

The only `trusted-build-v1` pairs are Windows CMake `configure`, `build` and `canonical-build`, plus Windows direct-MSVC `direct-production` and `direct-tests-build`. Exact source, job, stage, argv and policy must agree in the producer, package validator and downloaded consumer. Every product/canonical test, source check, selftest, Linux stage, HTTP/provider fixture and other default caller remains `strict-v1`. No registry change, process breakaway, name exception or new process right is used.

Before deliberate teardown, observe the real owned root exit zero with no previous failure, overflow or expired deadline. Use only the assigned private job; require terminal root and empty job, one in-budget close attempt, real EOF/readers, stable complete streams and declared output/readiness checks before success. After any close attempt, no later path may query, terminate or close that handle. Failure cleanup time is never successful execution time. Cached results are immutable; failed partial facts remain accurate observations or null, not fabricated success or all-false history.

The direct test wrapper gains mutually exclusive `-BuildOnly` and `-RunOnly` modes. Invalid combinations and phase-only parameters in default mode fail before side effects. Default invocation continues its combined canonical compilation and execution, including existing `-SkipProductionBuild` and additive `-TestSources` behavior. Both wrappers check setup, directory changes, compiler, linker and copy for exact zero, including negative/high-bit statuses without trusting a shadowed ERRORLEVEL variable. Canonical test execution preserves its actual 32-bit nonzero status even if later report writing fails.

The fixed direct-MSVC commands are:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-tests-cl.ps1 -SkipProductionBuild -BuildOnly -ProductionManifest <output>/reports/direct-production-objects.json -PhaseContext <output>/reports/direct-tests-build-context.json`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-tests-cl.ps1 -RunOnly -PhaseContext <output>/reports/direct-tests-build-context.json -RunReport <output>/reports/direct-tests-run-context.json`

Compilation receives 1,200 seconds and strict execution 600 seconds, with one shared 1,800-second deadline including setup, handoff, hashing and pair publication. This does not double the previous combined allowance. The strict phase preserves `build/cl` cwd, the independently selected developer/runtime setup, the pinned canonical binary and its true exit. Its stdout alone supplies the required sixty-group log. The build phase never executes tests; the run phase never compiles, links, copies or cleans objects.

The direct producer records the exact 53 production objects and 51-object test-link subset, with no raw object archive. Verify consumed identities before/after test compilation and pin the canonical executable after owned teardown. Compare the wrapper's prepared copied-binary observation to that final descriptor before declaring context ready. Runtime context stores bounded identities/descriptors rather than raw environment values. Unknown, missing, changed or partial inputs fail.

Windows CMake configure readiness checks the fixed VS17-2022 layout, eight selected cache facts and seventeen generated regular files. It keeps descriptors and selected facts, not cache/project contents, and rechecks the handoff before build. Readiness-file controls therefore exercise the actual producer; consumers verify the bound reports but cannot reconstruct omitted generated bytes. A different generator fails pending review.

Qualification and stage records use their `-v2` schemas. New exact-key reports are capped at 12 KiB for production objects, 2 KiB for each phase context, 4 KiB for pair timing and 8 KiB for configure readiness. Standalone reports use bounded canonical ASCII JSON, BOM-free UTF-8 and exact LF/CRLF forms, with duplicate/unknown-key and ordinary-type validation on Python and Windows PowerShell 5.1. Complete, prepared and failed states are distinct.

Report bindings are acyclic: manifests precede sealed phase results; the pair references those results; only qualification-level metadata binds the pair after its write/readback/hash deadline check. A late pair publication preserves phase facts but fails pair/qualification, blocks later stages and cannot accept a stale complete-looking file. Every interval, including run start <= run end, is checked. No file hashes itself.

Failure diagnostics retain a fixed role-specific partial packet. Direct-phase failures retain critical new reports and at most one prior result. Later strict failures prioritize the current failing report tails; they do not silently add earlier context/readiness reports or extra raw logs. Missing earlier bytes remain unverified. The largest selected raw-role fixture is 180 KiB /245,776 base64 bytes. Complete selected-fact retention is conditional on admission: both LF and whole-file CRLF must have metadata <=12,288 bytes and total <=256 KiB before a destination is created or changed. Oversized valid metadata is incomplete/HOLD, not qualification. Preserve the original error before optional persistence and report record/collector failures separately; a failed local record does not prevent the collector attempt. No selected fields, roles, raw-tail limits or error-prefix/hash conventions are weakened.

Required controls include actual dispatcher/argument forwarding and preserved default batch behavior, Windows parser and real tiny exit/cwd/environment cases, both ownership policies through ordinary and late finalization, immutable repeat completion, output/object changes, deadline/close/storage failures, complete retention and consistently rehashed policy/report/source/binary/log substitutions. Default compatibility through those API controls is not a second full compiler run. The new native qualification must execute real BuildOnly and strict RunOnly, all four jobs and every existing product gate. Native timing, source size and archive fit remain measured gates; the 120-second helper limit is unchanged.

Source and public declarations remain frozen with native/outcome pending. A successful plan review or local control run does not establish native acceptance.

Failed source-control diagnostics use qbrain-n49d-source-controls-failure-v2 ordered pairs/triples. Decoding preserves every original row, outcome, trace and order. Successful output stays unchanged. Complete LF/CRLF forms must fit the 64 KiB stream role; unavailable encoding remains incomplete failed evidence.
