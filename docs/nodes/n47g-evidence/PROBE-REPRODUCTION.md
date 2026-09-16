# Additional transaction probe provenance and reproduction

This is review tooling only, not a product target. The probe source and report
are the exact locally executed bytes; their SHA256 values are in SUMMARY.json.
Use the unchanged product at b1292b54543b9f54cd5e2b71f4ae4bf5f6247385 (tree
572dce7081140b7869821e9e2f98b7f1429d6328) for all headers, fixtures and libraries.
Do not compile against a moving main and reuse the report's source attribution.

In a separate Linux source checkout, configure the original CMake project with
QBRAIN_WITH_PG=OFF, build qbrain_lifecycle_batch_tests, then compile this probe
with C++20 and include paths for the repository root, include, third_party and
third_party/sqlite3. Link to the same static libraries in the same order emitted
by `ninja -t commands qbrain_lifecycle_batch_tests`, replacing only the test object
and output name. Do not define QBRAIN_BATCH_STANDALONE for this probe: it provides
its own main. Invoke the resulting executable with a new JSON output path.

It includes the original test translation unit to reuse synthetic seeding and
small helper functions; it does not invoke the original scenario runner. New
checks compare raw SQLite policy/revision/object/timestamp snapshots rather than
comparing the production result to itself. The declared source_commit in its
output is a fixed attribution to the source used during this outcome review,
not a runtime Git measurement; source bytes were separately reconstructed and
matched. Counts include helper assertions and are not distinct user scenarios.

Observed here: GCC14.2.0 on Linux, five scenarios/67 assertions passed. No new
Windows or signed-in client execution by this probe. The original native and
ASan/UBSan evidence is separately recorded. Use disposable fixtures only. This
is not a request for the owner or their local Agent to install compilers or rerun.
