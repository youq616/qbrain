# N47F review correction: do not coerce malformed time storage

Candidate reviewed: f585eed02e62a8a333ef5fcd8263019c618ecc2f.
The complete native workflow 35059423059 passed, but an additional real-CLI
experiment found an advisory-age defect not covered by the original tests.
An isolated synthetic brain with memory_items.created_at stored as TEXT
`123not-a-timestamp`, REAL `123.75`, or BLOB bytes `123` reported stale and time123.
The C++ column_int accessor follows SQLite conversion, so a malformed timestamp
was presented as a legitimate age. This is a P2 data-quality/diagnostic defect;
it did not create a fact, change truth status or bypass evidence/source checks.

## Narrow correction approved before implementation

Inspect typeof(created_at) in the existing bounded per-support SELECT. Accept
only INTEGER storage for advisory time; non-integer storage is unknown, with
null age and latest_valid_support_created_at. Preserve existing negative/zero
unknown, future clock_anomaly and newest-valid-support handling. SQLite INTEGER
affinity may already convert exact numeric input to INTEGER, which remains valid.

Also validate typeof(archived_at) before interpreting archive metadata; malformed
non-integer archive timestamps fail with fact_lifecycle_invalid_metadata rather
than silently truncating. This never makes an archived fact a recall anchor and
never hides mandatory direct counter-evidence. No schema migration, source/write
permission change, inferred truth, provider call or new automatic operation.

Add a named C++ scenario for TEXT/REAL/BLOB storage, a valid integer control,
null advisory fields, unchanged revision, and malformed archive metadata. Require
that scenario in the source-bound unit report; negative report tests must reject
the old scenario set. Keep all previous assertions, including the read-only
transaction-authorizer fix, and rerun native CI on the changed candidate.
The prior green package is not sufficient evidence for the fix and is not promoted.

## Outcome-pass environment

Clang17 AddressSanitizer build succeeded here, but execution failed before main:
ReserveShadowMemoryRange could not reserve the required virtual address range
under this runtime's 4TiB RLIMIT_AS hard limit. Record ASan execution BLOCKED,
not PASS and not a product defect. A separate UBSan build and real original
lifecycle16/153, old recall15/330 and process36/58 tests passed. Do not weaken
assertions or silently claim AddressSanitizer ran; retain the failed log.

Engineering plan review: approved for the strict-storage-type correction and
falsifiable tests. Owner-authorized separate engineering self-review, not an
independent subagent or third party. Final outcome/native acceptance remains pending.
