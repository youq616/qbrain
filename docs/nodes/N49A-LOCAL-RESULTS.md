# N49A local combined-tree evidence and remaining gates

Status: development candidate; native Windows qualification and final non-author
outcome review are pending. No release, main-merge or stable-product claim.

## Actual integration

The candidate preserves genuine ancestry from e0a27f829 and the exact accepted
PR62 848ef980, PR64 d57e6b32 and PR66 1132c97f heads. PR65 0e3c1239 is contained
once through its descendant PR66. All 62 inherited changed files retain their
canonical Git bytes; no product overlap required a behavior change. The new
executable links the combined production code, rather than separate copies of
the individually accepted products.

PR61 fixed-e0a packaging was not needed or retargeted. PR63/67/68 are excluded.
The source guard verifies these unique candidate commits are not ancestors,
without incorrectly excluding their shared historical ancestors. CMake and
direct-MSVC list the same 51 production translation units; the canonical test
linker has 50 production objects and 59 test sources registering the original
60 groups. Both original build scripts and the original55 driver are unchanged.
Windows checkout validation allows only exact LF-to-CRLF conversion, reporting
each such file; a 70-file conversion control passed and a non-newline mutation
was rejected. Three inherited trailing-space lines in stage_n48x_runtime.py are
preserved rather than rewriting an accepted module.

## Fresh local execution

Tools: GCC 14.2.0, workspace-local CMake 3.31.10 and Ninja 1.13.0. SQLite only;
all data synthetic, no model account, real client, user database or PG service.

- Combined Debug CMake: 34/34 registered portable CTests passed. The original
  Windows-specific aggregate qbrain_unit was not substituted with a portable
  count; its unchanged 60-group native gate remains required.
- Both Debug and Release products passed the 15-step combined process driver:
  normal and Python -O context invalidation each 57 scenarios/117 CLI calls/
  3,646 checks; logical observation each 18 commands/2,679 checks; runtime
  observation each 19 checks; observation semantics each 18 commands/54 checks;
  original context65, Hook69 and memory44 on both modes.
- The original SQLite context contract passed 68 checks. Existing focused
  suites on the combined code retain context invalidation57, preflight284,
  coverage367, query-cache59/integration51, logical86, rerank-move182,
  runtime55 and observation-semantics408 checks.
- Ten fully linked ASan/UBSan focused programs passed with empty diagnostics
  only when local leak detection was disabled. Default LeakSanitizer exited
  with its explicit ptrace-environment fatal error after passing test bodies.
  Original failures are retained. This is supplementary address/undefined
  behavior evidence, not leak qualification; CI keeps leak detection enabled.

## Preserved failures and independent-review correction

The first original55 invocation stopped at step52: the 47 MiB Debug ELF exceeds
OpenCode's unchanged 32 MiB executable bound. A fresh 6.3 MiB Release build
closed that lifecycle failure without raising the bound or altering any test.
Its lifecycle gate passed all 16 driver substeps, including the normal/-O
70-check OpenCode configuration/process fixtures.

The Release original55 invocation then stopped at step53 before receipt commands:
the unchanged receipt fixture rejects an arbitrary locally rebuilt historical
binary. Therefore **original55 has not passed locally**. Supplementary execution
used that unchanged fixture's explicitly supported --baseline-source option on
a clean ad31f404 source checkout. All 18 retained script/readback steps passed,
including 123 receipt checks and 156 commands. The final MCP fixture separately
passed 172 checks/96 commands and its negative readback controls. These separate
results are not relabeled as the original55 aggregate.

The published Windows historical comparison ZIP was independently downloaded
and checked: archive c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d;
qbrain.exe 838955a0ad88779af08c53396b773d62b327cccd4f216a18379f0a76ffa4c9cf,
4,130,304 bytes. That executable is accepted by the original receipt identity
gate. It was not executed here or used to certify the new combined product.

The initial 272-check new cross test passed but independent review found two
false-warm setup assumptions: save_config_value reloads configuration and clears
query vectors. Its ACL and memory-policy assertions therefore did not prove the
promised warm-cache case. The correction warms under an allowed source, changes
only synthetic DB policy rows without reload, and asserts retained entries before
and after ACL rejection, capture, extraction and forget. Observer-active denial
still requires zero logical/HTTP calls and unchanged hit/load counters. The
process driver now isolates HOME/USERPROFILE/APPDATA/LOCALAPPDATA per subprocess.
Earlier output is retained as pre-correction evidence, not warm-cache proof.
The repaired cross test passed 280 checks on fresh Debug, Release and
ASan/UBSan-without-local-leak-detection builds, with empty diagnostic streams.

## Required next gates

The exact frozen repair must receive source/portable prepublication review.
Only then may a new non-main development branch be published to run the exact
candidate workflow. That workflow requires Windows CMake original60 and focused
tests, unchanged original55 with its pinned historical fixture, real numeric
loopback HTTP attribution, separate fresh direct-MSVC original60 plus cross-test
link/run, and leak-enabled sanitizer qualification. Final non-author outcome
review must bind to that resulting tree and actual native artifacts.

Persisted embedding-space identity, real-client memory consumption, real-model
quality/full-cost evidence, other PG parity, signing and Issue40 remain separate
open boundaries. No silent reindex, real installation or release was performed.
