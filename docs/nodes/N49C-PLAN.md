# N49C — integrate qualified client and retrieval capabilities

Status: approved for bounded implementation after separate non-author plan review.
Approved technical plan SHA256: 3733a1be92f32545e0fac39c3f8d1cce546f83b177b7e55b2261c7b80c0b30c6.
This repository edition includes the approved status notice and publication-identity clarification; native/outcome qualification is pending.

Prepared 2026-10-01 UTC. This is a new integration stage using already qualified
inputs. Frozen N49B work remains outside its scope.

## 1. Product goal and why one stage

Deliver one development candidate containing the accepted N49A cache/context/
observation integration plus the separately qualified PR68 directory-scoped
search and PR67 project-local Cursor adapter. N49A currently rejects search
--uri and its installer accepts only Claude/Codex. These are actual missing
capabilities in the integrated product, not new duplicate implementations.

A combined stage is justified because both incoming deltas are completely
disjoint from each other and from N49A's delta, while the delivered binary
shares CLI, Brain, search/AI/observation libraries and Hook/context behavior.
Two intermediate integration acceptances would still require the final combined
native/installer qualification. Preserve the independently accepted modules as
immutable inputs, perform one full combined qualification, and keep each
module's test results separately identifiable. This does not transfer old
PASS results to the new union.

No new runtime behavior or public operation is designed here. Existing model
identity limitations remain; this stage neither implements nor validates
persisted vector provenance, trusted vector derivation, reindex or PG cache
migration.

## 2. Exact source identities and proposed ancestry

Repository: https://github.com/youq616/qbrain

- Common historical base e0a27f829d970c24ed8c566023ada0911c0042b3
  tree 534c86deabf43e30d3b2533cd3bf1f0728cf8400
- N49A f5331d174b6dfb853fd5450c78a25ae2754681da
  tree ba064799fc7314c2674b50e764d52655aa31ecf2
  branch integration/n49a-verified-core
- PR68 d54308d61bc894f540885b9b317b899c560e58d2
  tree 4acd82c6e4205353ae3335ccd62eb8a37be6004a
  branch feature/n48z-directory-search
- PR67 8394e83aac484bf6c31fad421162d258fb8d2587
  tree 28bc9453fb0b651a06f9f8e06f00c1ed2db616d0
  branch feature/n48y-cursor-hooks

All three live refs and Git-data commit/tree identities were freshly read.
N49A local accepted checkout remains clean and detached at the exact source.
The Git-data recursive tree responses are untruncated. PR68/PR67 compare to e0a
as 13/3 commits ahead respectively; their common merge base with excluded PR61
and PR63 unique heads is e0a, not the excluded commits.

Proposed NEW branch: integration/n49c-client-retrieval. Remote inspection found
no refs matching integration/n49c-* at preparation time. Recheck before create;
do not overwrite an unexpected existing branch.

After plan approval, use a NEW local repository outside the accepted checkout.
Fetch only these exact permitted heads and their ancestry; do not fetch all
branches or copy another checkout's .git. Initial integration commit's ordered
parents must be [N49A, PR68, PR67] above. Additive qualification files may be
included in that commit. Subsequent authorized fixes must preserve these genuine
ancestors. Candidate commit/tree is deliberately not predicted or claimed yet.

N49A's recorded parents are e0a, 848ef980200b40101a1908fddfc0d829abc77d8d,
d57e6b32398fca4e59d80dcfab7c5af119dde2be and
1132c97fac1964f84eb593e91ace5bc774a3c98f, in that order. PR68's direct parent is
f384482f08812722b32c2e11ffcb57ba67d4ded7; PR67's direct parent is
ca16d6bd62aac6c224350e5f3c13e1f5f01494e4. No ancestry rewriting or cherry-picked
replacement is planned.

## 3. Immutable inventory and file ownership

Companion N49C-INPUT-INVENTORY.json is normative:
SHA256 5e0e87d28d2acb2a2409682b9d9618fc2a6bf43bba2b2c2392f7a6ba4ba40b0e

It records every N49A blob path/mode/object ID, all 72 N49A changed paths against
e0a, and every PR68/PR67 delta blob. These three delta path sets are pairwise
disjoint. There are no input deletions. The inherited product is exactly all
1,606 N49A blobs with the following 24 entries from the pinned incoming heads:
16 added files and 8 replacements, totaling 1,622 inherited files before new
N49C-only qualification/doc files. This inventory expression is not a performed
merge or a runtime qualification.

PR68 immutable entries (13):
- .ci/directory_search_targets.cmake
- .ci/test_directory_search.py
- .github/workflows/n48z-validation.yml
- CMakeLists.txt
- docs/nodes/N48Z-PLAN-AUDIT.md
- docs/nodes/N48Z-PLAN.md
- include/qbrain/cli/search_arguments.hpp
- include/qbrain/search/directory.hpp
- scripts/build-cl.ps1
- scripts/build-tests-cl.ps1
- src/qbrain/cli/commands.cpp
- src/qbrain/search/directory.cpp
- tests/test_directory_search.cpp

PR67 immutable entries (11):
- .ci/cursor_hook_targets.cmake
- .ci/test_cursor_hooks.py
- .ci/test_cursor_install.ps1
- .github/workflows/n48y-validation.yml
- docs/nodes/N48Y-PLAN-AUDIT.md
- docs/nodes/N48Y-PLAN.md
- include/qbrain/integration/detail/cursor_hook.hpp
- include/qbrain/integration/detail/hook_trace.hpp
- scripts/Install-QbrainMemory.ps1
- src/qbrain/integration/hook.cpp
- tests/test_cursor_hooks.cpp

All other inherited paths, including N49A's 72-path delta, old tests, ledger,
source checker and workflows, retain exact Git blobs and modes. Accept only
exact documented Git LF-to-CRLF checkout conversion during byte verification,
not a whitespace-insensitive comparison. Do not rewrite inherited plan/audit
history or mark old documents current by editing their assertions.

The sole author owns new N49C qualification and documentation files:
- .ci/check_n49c_sources.py
- .ci/test_n49c_source_contract.py
- .ci/client_retrieval_integration_targets.cmake
- .ci/build_n49c_direct_tests.ps1
- .ci/test_n49c_process.py
- .ci/run_n49c_installers.ps1
- .github/workflows/n49c-integration.yml
- tests/test_client_retrieval_integration.cpp
- docs/nodes/N49C-PLAN.md
- docs/nodes/N49C-PLAN-AUDIT.md (completed separate plan-review summary)
- docs/nodes/N49C-LOCAL-RESULTS.md (prepublication results only; no native PASS)
- docs/nodes/N49C-HARD-AUDIT.md (prepublication PENDING notice only)
- docs/nodes/n49c-evidence/INPUT-INVENTORY.json
- docs/integration/CLIENT-RETRIEVAL-CANDIDATE.zh-CN.md

The three audit/results documents above are frozen BEFORE publication. The
HARD-AUDIT notice must state that exact-candidate native qualification and final
non-author outcome review are pending; it must not contain a final PASS or a
future candidate SHA. LOCAL-RESULTS records only results actually available
before the source freeze and their tested input identity. It does not certify
an as-yet-uncreated Git commit. Final native evidence and the actual independent
outcome report are retained OUTSIDE this source tree, as specified in section 7.
In-tree plan status remains approved/pending rather than retrospectively done.

No additional source/configuration path changes are permitted without an explicit
plan amendment and renewed independent review. If a genuine integration defect
requires changing an inherited runtime/build blob, stop and report the exact
conflict instead of quietly breaking this preservation contract.

## 4. Workflow contracts and complete build closure

Historical .github/workflows/n49a-integration.yml has push limited to
integration/n49a-verified-core, no pull_request trigger, and workflow_dispatch.
It WILL NOT automatically run on the new integration branch. Leave its bytes
and triggers unchanged. Do not manually dispatch it at the expanded candidate:
its source checker correctly excludes PR67/PR68 and protects the pre-directory
build lists. Such a scope rejection would not be a new product PASS or a reason
to remove the old gate. Any historical replay must target exact f533 only.

Likewise N48Y/N48Z push triggers remain restricted to their original feature
branches. N48Y's protected-diff check is incompatible with N49A additions;
do not dispatch or modify that historical workflow for the new union. Run the
unchanged underlying tests through the explicitly new N49C workflow instead.

New N49C workflow triggers only the new branch's pushes plus explicit dispatch,
pins checkout to the event SHA, uses read-only contents permissions, preserves
credentials=false, retains raw evidence on failures, and never writes source
or advances refs in CI. Use a depth-1 exact-SHA checkout followed, only where
ancestry is needed, by an explicit no-tags/no-submodules fetch of that exact
candidate SHA and its reachable accepted ancestry. If unshallowing is required,
name the exact candidate SHA in that fetch; never use fetch-depth: 0, --all,
unqualified branch fetches, wildcard refspecs or all-ref checkout defaults.
Verify the shallow boundary is actually removed before claiming full ancestry.
Author setup likewise fetches only the three pinned accepted heads. Any fixture
commit is either already in that accepted ancestry or fetched by its exact
listed commit, not by a branch or tag wildcard. No PR creation, main update, release or deployment is
part of this plan. Existing path-filtered PR workflows would need separate
tracking if a draft PR is later authorized; do not silently count them passed.

New source checker must independently verify:
0. Bind the normative inventory bytes to the approved fixed SHA256
   5e0e87d28d2acb2a2409682b9d9618fc2a6bf43bba2b2c2392f7a6ba4ba40b0e.
   This digest covers canonical raw Git-blob bytes, before checkout newline
   conversion. The checkout copy must match that blob exactly or its exact,
   documented LF-to-CRLF conversion; no other normalization is allowed.
   The checker has this literal expected digest outside the inventory itself;
   the workflow independently hashes the raw inventory blob at C before
   executing the checker;
   the non-author review independently compares the published blob with the
   approved external plan/inventory. An editable inventory's own claim is not
   authority. Every job pins its actual source SHA/tree and checks source
   cleanliness after execution, including failure paths.
1. The exact ordered input parents for the initial candidate and genuine
   ancestry thereafter; all already-accepted N49A ancestors remain present.
2. Exact expected inherited file set, modes and blobs from the pinned inventory;
   precisely N49C's allowlisted additive paths and no deletions or other edits.
3. Unique excluded PR61 4fb5f7bcc4d5871b7eef409963806ba58b486ae1 and PR63
   18abbe94dff60f85298b2743efc02839f869cd77 are not ancestors. No frozen N49B
   content is fetched, read or added. Do not reject their shared legitimate e0a
   ancestor. Exact union checking, not ref-name filtering alone, enforces scope.
4. Original tests/test_main.cpp remains exact with the original 60 unique
   registrations; .ci/run_n48i_checks.py, run_n48e_checks.py,
   run_n48d_regressions.py and validate_native_log.py retain exact blobs.
5. PR68's CMake/direct-MSVC lists include directory.cpp/directory.obj in the
   production compile and both production/test link sets. Compare all source
   sets and object basenames, detect omissions/duplicates/collisions, and derive
   counts from actual inputs rather than retaining N49A's historical counts.
6. CMake's single new wrapper includes verified_integration_targets.cmake,
   directory_search_targets.cmake and cursor_hook_targets.cmake exactly once,
   then registers the new integration test. No duplicate inherited registrations.
7. A source-checker validation suite detects wrong/missing/extra source metadata
   and unacceptable inventory changes. This is ordinary static source-contract
   checking, not any frozen runtime-review scenario.

The N49A direct cross-test linker dynamically reads current direct object lists
and can remain unchanged. Run it after fresh direct builds. The NEW N49C linker
must similarly derive actual objects and build its separate-main integration
test; do not append a second main through the original TestSources mechanism.
Keep every inherited test assertion and timeout unchanged.

## 5. Combined behavior gates

Use only synthetic fixtures in disposable HOME/USERPROFILE/APPDATA/
LOCALAPPDATA/project roots. Remove provider/PG credentials from test environments.
Network is zero external provider traffic; existing deterministic loopback
HTTP fixtures are allowed. Preserve no-vector, consent, default-read-only,
source scope, privacy and unknown-cost semantics.

A. Directory plus observation
- Run unchanged PR68 unit and actual CLI process suites in normal/Python -O.
- Retain exact source/namespace/directory-prefix filtering before ranking,
  nested/UTF-8/neighbor/deleted-page and out-of-scope crowding assertions.
- On the combined real CLI path, invalid directories fail before embedding;
  --no-vector and conservative suppress QUERY EMBEDDING independently of any
  explicitly permitted reranking. They do not promise zero provider work when
  an LLM rerank is explicitly enabled by flags or tokenmax mode.
- Explicit directory/observation matrix, always using synthetic data:
  - Invalid directory: no embedding, rerank or HTTP work
  - --no-vector with balanced mode and no rerank: zero query embedding and
    zero provider work
  - Conservative mode with no rerank: zero query embedding and provider work
  - Conservative with local --rerank only: zero query embedding and HTTP work
  - Conservative --rerank --rerank-llm with deterministic configured loopback:
    zero query embedding; permitted LLM rerank gets genuine logical/HTTP records
  - --no-vector --mode tokenmax with deterministic configured loopback: zero
    query embedding; permitted mode-enabled LLM rerank is observed accurately
  - Balanced vector-enabled query: permitted embedding is recorded accurately;
    no actual HTTP event is invented for an entirely local/mock outcome
  Fixture setup must supply matching results so intended rerank paths are
  exercised, and must retain unknown/error semantics without guessed usage or
  costs. All external paid/provider traffic remains prohibited. No inherited
  runtime change is needed to satisfy this corrected matrix.
- Valid scoped query embedding is accurately associated with N49A logical/
  actual HTTP observation, using deterministic accepted provider fixtures.
  Errors/unknown usage remain unknown; no prompt/key/body appears in metadata.
- Ordinary search without --uri retains N49A's existing cold/warm cache,
  permission and live-evidence behavior; rerun its unchanged cross suite.
- PR68 currently calls embed_texts directly for directory queries. Do NOT claim
  query-vector caching there, add that feature, or change persisted-vector
  compatibility rules as part of this integration.

B. Cursor plus shared context/search
- Run unchanged Cursor unit and actual binary process suites, normal/Python -O.
- Cover the accepted five-event contract, single installed/current workspace,
  only sessionStart additional_context, stable generation identity, explicit
  capture and promotion consent, source separation, withdrawal and privacy.
- New combined fixture drives the actual Cursor adapter on synthetic events,
  then reads the resulting permitted source through existing context and
  --uri .../memories/ text-only retrieval. Verify committed visibility,
  source separation and deletion/withdrawal behavior through public APIs.
  Do not introduce a new fact-consumption or memory-receipt meaning.
- Invalid/unsupported event remains fail-open and cannot perform disallowed
  work. Preserve existing input bounds and exclusion of transcript/attachments.

C. Windows installation/ownership

Run every row below twice: once with the actual Windows PowerShell executable
at $env:SystemRoot/System32/WindowsPowerShell/v1.0/powershell.exe (major 5), once
with the discovered pwsh executable (major 7). Record executable path, version,
actual major, argv, exit, raw stdout/stderr and report digest. Let S be that
executable, M its verified major, C the frozen candidate commit, and B the
absolute path of the FRESH DIRECT-MSVC COMBINED qbrain.exe. B's SHA256 is recorded
before/after the matrix and used for EVERY -Binary/--binary argument, including
old-installer negative controls. No old downloaded EXE is executed or substituted.

Installer/fixture identities:
- I = the combined candidate's scripts/Install-QbrainMemory.ps1, exactly PR67
  Git blob 631cb4ebee7f4ef40cb57c8370ad6febcb23c3d8
- P = scripts/Install-QbrainMemory.ps1 from snapshot-prior commit
  3ebecf26946ae6ddd04fb018085ffc023b5fcab0, exact Git blob
  ff7042fa94b3d6a7b85e06572557fe575ad18c74
- K = scripts/Install-QbrainMemory.ps1 from case-path-prior commit
  98b45d264696a23552ca14d12218555c57087528, Git blob
  90bf59912a58203de600c2ecaf970c7c5a183236. First verify the raw 14,924-byte,
  LF-only blob has SHA256
  bde21f5c1aabb7b517a1324f3fb076b482a5652387eaab26a1050bb0feb97dd2.
  ONLY for K, then explicitly convert each LF to CRLF outside tracked source;
  verify the executed fixture SHA256 is
  d802c230d2e5b0938b81baa115d5cf5b475aa855fce0df28f0305f00575fcc51
  before use. No BOM, encoding change, other whitespace change or implicit
  platform-default conversion is permitted.
- R = scripts/Install-QbrainMemory.ps1 from the fixed published ZIP
  https://github.com/youq616/qbrain/releases/download/windows-preview-c26ec5e5/qbrain-windows-x64-reviewed.zip
  ZIP SHA256 ec681a4599bf1b2a90f3848f5bf65b6d6a32e37254f32392d0709c43080b356c;
  installer SHA256
  99d864bf1e87c75a2b7c22a7f2c27d3b25210a153ef10516e9fff366313a22a6

Validate these distinct identities BEFORE use. Materialize fixtures outside
tracked source and retain their hashes in evidence. P remains exact raw Git
bytes; R remains exact pinned ZIP-member bytes. K alone uses the explicit,
identity-checked LF-to-CRLF conversion above; no other rewriting is allowed.
For each matrix row, Q is a unique report path containing shell M and row name;
L is its corresponding raw log. All paths/scripts in the matrix are rooted at
the exact candidate unless explicitly P/K/R. All test and validator source bytes
are unchanged inherited inputs. Each S invocation uses -NoProfile -NonInteractive
-ExecutionPolicy Bypass -File followed by the arguments shown. ExecutionPolicy
here is the inherited process-local invocation flag, not a system-setting edit.

| Row | Harness (run for BOTH M=5 and M=7) | Fixture/test invocation | Expected exit | Binary |
| --- | --- | --- | --- | --- |
| Cursor install | S | .ci/test_cursor_install.ps1 -Binary B -Report Q (I implicit) | 0 | B |
| Original hooks | S | .ci/test_install_hooks.ps1 -Binary B (I implicit) | 0 | B |
| Original consent | S | .ci/test_install_consent.ps1 -Binary B (I implicit) | 0 | B |
| Windows transport | S | .ci/test_windows_transport.ps1 -Binary B | 0 | B |
| Fact install | S | .ci/test_hook_fact_install.ps1 -Binary B -Report Q (I implicit) | 0 | B |
| Promotion install | S | .ci/test_promotion_install.ps1 -Binary B -Report Q (I implicit) | 0 | B |
| Current recovery | S | .ci/test_installer_recovery.ps1 -Installer I -Binary B -Report Q | 0 | B |
| Recovery readback | Python, associated with M | .ci/check_recovery_report.py --report Q --installer I --binary B | 0 | B |
| Recovery prior | S | .ci/test_installer_recovery.ps1 -Installer R -Binary B -Report Q | EXACTLY 1, expected old defects | B |
| Prior recovery readback | Python, associated with M | .ci/check_recovery_report.py --report Q --installer R --binary B --baseline | 0, expected rejection verified | B |
| Current snapshot | S | .ci/test_installer_snapshot.ps1 -Installer I -Binary B -Report Q | 0 | B |
| Snapshot readback | Python, associated with M | .ci/check_installer_snapshot_report.py --report Q --installer I --test .ci/test_installer_snapshot.ps1 --binary B --source C --shell M | 0 | B |
| Snapshot prior | S | .ci/test_installer_snapshot.ps1 -Installer P -Binary B -Report Q | EXACTLY 1, expected old defects | B |
| Prior snapshot readback | Python, associated with M | .ci/check_installer_snapshot_report.py --report Q --installer P --test .ci/test_installer_snapshot.ps1 --binary B --source C --shell M --baseline | 0, expected rejection verified | B |
| Case paths | S | .ci/test_installer_case_paths.ps1 -Installer I -BaselineInstaller K -Binary B -Report Q | 0 including expected baseline cases | B |
| Case readback | Python, associated with M | .ci/check_installer_case_paths.py --report Q --installer I --prior K --test .ci/test_installer_case_paths.ps1 --binary B --source C --shell M --log L | 0 | B |
| Snapshot validator self-test | Python and Python -O, associated with M | .ci/test_check_installer_snapshot_report.py | 0 in each mode | Synthetic report fixture; not binary execution |
| Case validator self-test | Python and Python -O, associated with M | .ci/test_check_installer_case_paths.py | 0 in each mode | Synthetic report fixture; not binary execution |

Each validator reads the immediately corresponding producer's exact report,
installer, test, binary and log as applicable. Recovery validator has no --shell
parameter; additionally parse the recorded powershell version string and verify
its major equals M, retaining the raw version string and shell identity. No expected exit 1 is
accepted without its matching baseline validator succeeding. No short-circuit
may hide remaining rows. The original55 label does not subsume this matrix.

Verify install/status/idempotence/uninstall, default capture off, independent
fact permissions, unrelated-entry preservation, collision/external-edit refusal,
before-images, late failure/recovery and exact owned entries. Actually invoke
generated Cursor commands and retain stdout/stderr/exit data. PS5/PS7 describes
the outer installer harnesses; the accepted generated Cursor bridge itself uses
Windows PowerShell 5. Do not report two product runtimes. Install only into
disposable CI fixtures, never a real user project/account. Signed-in Cursor
consumption remains unqualified.

## 6. Fresh native, original regression and sanitizer gates

The new workflow uses separate fresh jobs/output roots and exact-SHA evidence:
- Windows CMake product plus original60, every inherited N49A portable/focused
  target, PR68/PR67 targets and new combined tests. Run CTests and unchanged
  .ci/run_n49a_process.py, plus new directory/Cursor process checks.
- Windows unchanged original55 via .ci/run_n48i_checks.py against this new
  executable and the same historical N47X comparison ZIP, SHA256
  c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d.
  Preserve the exact fixture verifier, all 55 steps and limits. The old binary
  is a comparison fixture, never certification of the new executable.
- Ubuntu fresh CMake product and all supported inherited/additive CTests and
  process gates. Portable results cannot replace Windows native acceptance.
- Windows fresh direct-MSVC production + unchanged original60, existing N49A
  standalone cross test, new integration test, directory and Cursor process
  tests against the direct binary. Run both-shell installer/ownership checks
  against that same identified combined binary.
- Fresh fully linked Clang ASan/UBSan with leak checking explicitly enabled
  (ASAN_OPTIONS includes detect_leaks=1), running ALL 15 named targets:
  1. qbrain_verified_integration_tests
  2. qbrain_context_invalidation_tests
  3. qbrain_context_preflight_tests
  4. qbrain_context_coverage_tests
  5. qbrain_query_cache_tests
  6. qbrain_query_cache_integration_tests
  7. qbrain_logical_observation_tests
  8. qbrain_logical_rerank_move_tests
  9. qbrain_runtime_observation_tests
  10. qbrain_observation_semantics_tests
  11. qbrain_directory_search_tests
  12. qbrain_cursor_hook_tests
  13. qbrain_hook_trace_tests
  14. qbrain_hook_fact_tests
  15. qbrain_client_retrieval_integration_tests
  Pin target inventory, binary hash, instrumentation/build commands, effective
  sanitizer options, exit and raw stdout/stderr per target. Every target must
  actually start and finish successfully, with empty diagnostic stderr. Fail on
  sanitizer diagnostics/nonzero exits. A ptrace/address-space/environment
  failure is NOT a PASS; preserve it and await a supported runner result.
- Existing accepted loopback wire gates remain actual wire tests, not mocked
  replacement assertions. Per-target source/command/stdout/stderr/binary hashes
  must be retained. Derive case counts from fresh executable/report outputs.

Job budgets may accommodate the expanded workload without relaxing individual
test conditions. Keep jobs bounded and retain failures; split job scheduling if
needed without omitting any gate. No new PG server/DSN or paid provider is used.
QBRAIN_WITH_PG=OFF for CMake; direct scripts may discover libpq as before, but
scrub DSNs and report all PG execution as skipped/not qualified.

## 7. Review, source freeze and external outcome evidence

1. Obtain separate non-author review of THIS plan and the fixed inventory, then
   record plan approval before implementation. The plan-review summary may be
   copied into the candidate before source freeze. Public documents identify
   separate non-author review and technical scope; detailed reviewer identity
   remains in the external audit record without internal task-path names.
2. Build the inherited union and allowlisted qualification files. Complete local
   gates permitted by the approved plan and record their exact tested file/tree
   identity, failures and limits. Prepare all in-tree docs BEFORE publication:
   PLAN approved; PLAN-AUDIT completed; LOCAL-RESULTS prepublication-only;
   HARD-AUDIT explicitly pending final native/outcome review; user guide clearly
   a development candidate. None predicts a final native PASS or its own commit.
3. Freeze the source candidate commit C and tree T with all these documents in
   place. From this point no tracked file, including documentation, changes.
   Separate non-author prepublication review verifies C/T, immutable inherited
   inputs, the independently pinned inventory and additive source/local evidence.
   A correction creates a NEW candidate C/T and requires a fresh review.
4. After prepublication approval, publish only C by normal non-force update to
   the new development branch. Verify exact remote C/T, ordered parents and
   complete inventory. Initial publication is not native qualification.
5. Run all declared fresh native, original60/55, process, installer/transport and
   sanitizer gates at C. Monitor to terminal results. Keep raw artifacts and the
   final non-author outcome report OUTSIDE C's source tree. The report is written
   by the separate reviewer, not the implementation author, and must bind C/T,
   approved plan/inventory digests, actual run/job/artifact IDs and URLs, artifact
   SHA256/ZIP CRC, inherited blobs/modes, binaries, shells, commands, counts,
   failed/never-started gates and retained limitations. Store a hashed external
   evidence bundle; source-embedded pending notices are not the final review.
6. Only C/T with every required gate and final separate review PASS is bounded
   N49C-qualified. Report that exact C/T with its external evidence references.
   Do NOT commit a final PASS report or retrospective status edit into C.
7. Any later documentation-only or code commit D is a DIFFERENT, UNQUALIFIED
   commit/tree. If desired, D may contain the historical outcome report clearly
   labelled as evidence for C only, but cannot inherit C's qualification. To
   qualify D, freeze D and rerun the SAME complete plan gates and non-author
   outcome review at D, retaining D's final report outside D. No docs-only waiver
   or post-test evidence commit is implicit. Leaving C's in-tree pending history
   unchanged is intentional and avoids a self-referential audit dependency.

No project-complete, main-merged, real-user Windows11, real Cursor/model-quality,
real PG or release claim follows from bounded C/T qualification.

## 8. Boundaries, rollback and current unresolved evidence

Do not inspect, modify, run, recreate, publish or retry frozen N49B second-
boundary work or the blocked PR63 operation, including under a new name/tool.
Do not copy frozen candidate inputs into this workspace. Input union contains
only the accepted three sources. PR61 delivery/tooling is excluded as well.

Preserve N49A branch/checkout, all prior PR heads, main, tags/releases and all
original source/gate history. No automatic reindex, schema migration, credential,
global configuration or user-host change occurs. Rollback is discarding the new
development candidate; fixture cleanup removes only test-owned disposable data.
Do not delete published branches or user data as an implicit rollback action.

There is no textual-path collision in the pinned deltas. There is intentionally
a historical-checker scope collision, handled by a NEW contract, not weakened
old guards. Combined compilation, link order, observation associations,
installer behavior and native evidence are still unverified and are the work
of this stage. Current source-qualified history is background only.

The input identities and immutable union are verified by read-only inspection.
No merged candidate, test result or publication is established by this DRAFT.
Execution requires the recorded plan gate; qualified final evidence must follow
the source-freeze policy above. Repository-facing documents contain only the
engineering plan, source identities, test contracts, evidence and limitations;
private notes, internal task paths and coordination/tool bookkeeping are excluded.


## Approved publication identity clarification

If the publication connector cannot preserve the local commit metadata, create
only the corresponding remote Git commit object first, without advancing a
branch. A separate non-author check must verify its exact tree, ordered parents
and complete inherited/additive inventory, then explicitly designate that
verified object as the frozen native-test C before updating the development
branch. No local binary hash or native outcome is transferred to that different
commit. Every later native artifact and final external outcome report must name
the actual selected remote C/T. If this separate object binding is unavailable,
stop before the ref update. No source rewrite or completed-native-report commit
is needed for this narrow metadata binding.
