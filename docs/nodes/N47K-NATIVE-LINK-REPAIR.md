# N47K follow-up: complete native object closure

Baseline candidate e9d8f3e140564e35f129c199066e2ec77d667a27.
Actual failed run35178697281, Windows job105065990875, compiled diagnostics.cpp
then failed LNK2019 for qbrain::integration::run_hook_diagnostics. The direct-MSVC
production source list includes the new file, but its explicit object link list
does not include diagnostics.obj. The test script's production-object closure
has the same omission. CMake builds passed because they use their own target list.
This is a release-blocking native build defect, not a user toolchain problem.

## Narrow correction approved before implementation

Add diagnostics to both explicit native link lists. Keep current source selection,
compiler flags, clean-object policy and all existing runtime semantics unchanged.
Add a fail-closed static test of the default production/test source and object
closures, including no duplicate stems, missing/extra objects, test/production
collisions and unknown list expressions. Exercise it before native compilation
and in portable checks in both validation workflows; it is not a substitute for
actual MSVC linking or native regression. No new runtime dependency.

Falsify the new check against unchanged e9d8f3e1 and with synthetic omissions of
production or test objects. Rerun the new tests on the patch, rebuild Linux, then
run current-source Windows full build/regression/package and inherited suites.
Keep the old failed runs and do not promote the old candidate. Complete a separate
outcome review of file-handle lifetime, bounds, privacy, read-only behavior and
normal Hook compatibility before merge and exact-byte release.

Plan review: approved for this build-closure correction and negative tests.
Owner-authorized separate engineering self-review, not third-party/subagent.
No source permissions, defaults, schema, provider or user-machine changes.
