# N46F original-source intake and engineering review

Date: September 13, 2026. Reviewer: ChatGPT under the owner's standing authorization;
engineering self-review, not an independent third-party audit.

**Intake: verified. Original implementation: not ready for final acceptance.**
This document and its correction patch do not merge N46F, certify Windows CI or
publish a new EXE. No further local source export or GitHub credential setup is
needed from the owner for this intake.

## 1. Original bytes and commit identities

The received `qbrain-n46f-source-handoff.zip` is 36,960 bytes, SHA-256
`1e60fb0b4a616ad3acb78f6f04b5cfa2afb80bf6292bd590ecb1c146c717e916`.
It contains exactly `n46f.bundle`, `n46f.patch`, `manifest.json`, `README.txt`.
ZIP CRC and both declared member sizes/SHA-256 values passed:

- bundle: 18,113 bytes, `8e452c8e3344f3c1f7fb39fe1811aaa756d20dd54a875e7ecc3f497f5d76463c`.
- patch: 52,089 bytes, `dc14a49d8ca3da553fe0d16c92670b631760744cdafd45c502cff4bb761f25b2`.

The base source tree was reconstructed from the exact remote source archive and
unchanged historical source, and matched Git tree
`3d5eb0869f18cf1217e66fe1f37c4b5ab75c82b1`. Its commit object was reconstructed
from the repository's metadata and matched the original base SHA exactly.
The local inspection repository marks that base shallow; it does not claim to
have downloaded all earlier history. `git bundle verify`, import and `git fsck`
then succeeded without changing the owner's local repository.

| Identity | Exact value |
| --- | --- |
| Base | `48a498bbf2ea14b39f1023cd1d67e30fb98848f9` |
| Plan commit | `a0adf373c686d1bbc1845d58d84fb6d1b0da372c` |
| Plan tree | `39f96731d5c32d47f4987ea7dd5bb30219128e9f` |
| Implementation commit | `9426692fe40ba41880f9312534f02fde0459cfad` |
| Implementation tree | `e02873b759608a6ddd9d21f399dc7190cc2a6601` |

The parent chain is exactly base -> plan -> implementation. All 12 changed paths
match the manifest. Applying the supplied patch to a separate base index produced
exactly the implementation tree above. A regenerated format-patch differs in mail
formatting/signature trailers, not the applied source. Original files are retained.

## 2. Reproduced blocking and test defects

1. **Registered-group gate mismatch.** `tests/test_main.cpp` registers 48 groups,
   but both `.ci/test_validate_native_log.py` and the package gate still require
   47. Running the untouched gate produced `AssertionError: 48 != 47`: 8 tests
   passed and 1 failed. This would stop the portable workflow before compiling.
2. **Failure counts are incorrect.** The original CJK test records a FAIL row,
   then sets its pass count to the total list length. Actual execution reached
   20 PASS + 1 FAIL, but reported total=21/pass=21. This confirms the earlier
   5 PASS + 1 FAIL versus pass=6 report problem is in the source, not an inference.
   Failures raised outside check() can also discard earlier completed checks.
3. **ASCII fixture tests the wrong premise.** The fixture puts `QBCJKfixture`
   directly against a preceding Han run, then expects standalone ASCII FTS recall.
   The production run fails at `ascii_fts_still_works`, after the CJK and source
   cases pass. An independent ASCII-token page is needed to test unchanged ASCII
   behavior without introducing an ASCII substring fallback.
4. **Memory-budget fixture is never extracted.** The long message starts with
   `超长原话`, not a recognized explicit preference marker. A diagnostic run fixing
   only the preceding ASCII fixture then fails at `memory_limit_and_bytes`.
   Prefixing the synthetic message with `我偏好` exercises the intended budget.
5. **Invalid C++ hexadecimal escape.** `"a\xffb"` consumes b as part of the escape.
   GCC compiled it with an out-of-range warning; Clang rejected it. Splitting the
   literals as `"a\xff" "b"` represents the intended invalid byte sequence.
6. **Evidence gate accepts an empty list structurally.** all([]) and a zero count
   satisfy the new original conditions. Current workflow exit checks still help,
   so this is not a demonstrated malicious package; the independent evidence
   verifier nevertheless needs complete named checks and command exit records.

These are not grounds to broaden memory_read semantics. The original implementation
preserves memory::read, and actual memory literal tests pass. No assertion was
removed to repair the test suite. Timestamp ordering fixtures were also made
explicit rather than relying on wall-clock second boundaries and slug tie order.

## 3. Corrective patch and actual tests

The unapplied patch is committed in this repository at
`tools/handoff/n46f-review-corrections.diff` (same review branch as this document).
It is based ONLY on original `9426692`, not remote PR #12's different implementation.

Patch bytes: 17,148. SHA-256:
`909c507c9e018ea4f0d208c27b63dcaa3d3fcc0953b3770f8acf0fb484987564`.
Git blob: `e1b06b41347623d5faba2f14ff7fc4eea2b850a2` (repository readback matched).
`git apply --cached --check` and application in a separate original index succeeded;
the result is exact Git tree `11f24ab574f1519291b1780d1881d74eb98f9297`.
The inspection-only local correction commit is `ea34e05728e40e47d49c24ee11eb0d8d4e844965`;
that commit is NOT claimed to have been pushed as a product branch.

The patch changes six test/evidence files, not production src/ or include/:
48-group acceptance and old-log rejection, true PASS/FAIL counts, retained command
history, dirty-tree-aware report provenance, corrected fixtures and byte literal,
and a complete 31-name evidence gate with negative tests. Source identity, EXE
hash and script hash remain required. Do not apply it blindly to PR #12.

| Actual execution in this review environment | Result |
| --- | --- |
| Original production C++ application and focused targets, GCC/Linux | build succeeded |
| Original native-log gate | FAIL: 48 versus 47 |
| Original CJK process suite | FAIL: 20 PASS + 1 FAIL, false pass=21 summary |
| ASCII-only fixture diagnostic | FAIL at unextractable memory-budget fixture |
| Original classifier, GCC / Clang | GCC run passed with warning / Clang compile failed |
| Corrected classifier, Clang with -Wall -Wextra -Werror | build and run passed |
| Corrected CJK process suite against unchanged product implementation | 31 PASS / 0 FAIL; 54 actual child command exits all zero |
| Corrected log-gate unit suite | 10 tests passed |
| New report-gate unit suite | 7 tests passed, including expected simulated failures |
| Focused production memory/context CTest | 2/2 passed |
| Existing production process suites | config 6, memory 44, MCP 17, hooks 69, context 65, embedding search 11; total 212 passed |

One new report test initially omitted the normal detail field from its artificial
completed-check fixture and failed at diagnostic printing. That test-fixture error
was corrected and retained in local logs; it was not a product or original-source
failure. Existing memory_cycle observed one of its predefined lock retries. No new
retry-until-green policy or assertion suppression was introduced.

The tested Linux application SHA-256 is
`70659a68237d3fd7937decf6339103b5b58c9436a7d1e32176dfb025785c7699`.
It is not a Windows EXE or an officially published artifact. The production code
is unchanged between original and correction trees; source and test identities
must still be distinguished when integrating.

## 4. Integration boundaries still open

Remote PR #12 is a separate implementation at `515b80421a708ce80b75bbc3067b1d0e73aec853`,
which supplements the SQLite backend; this local implementation supplements the
shared hybrid layer. Do not stack both implementations. Review PostgreSQL behavior,
Unicode coverage and snippet behavior before choosing one integration path.

The prior PR #12 Windows run `34753274282` failed the existing HTTP handle-growth
check before its CJK/full-regression/package steps. It is not validation of local
`9426692`, nor proof that either CJK change caused the HTTP failure. This review
has not run new Windows CI, real PostgreSQL, paid models, Codex authentication or
logged-in Windows Agent sessions. It does not change main or publish a Release.

Source intake is complete. Further repository-side reconciliation and native
validation do not require the owner to export the same source again or install
compilers locally. N47 implementation is outside this review.
