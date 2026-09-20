# N47Y separate plan review

2026-09-20. Reviewer: coordinating ChatGPT, owner-authorized separate plan pass.
Verdict: APPROVED for the bounded receipt integrity correction.

The observed disagreement is reproducible, not a guessed historical cause: SQLite
TEXT affinity does not prohibit BLOB storage, and equality/uniqueness distinguishes
storage classes. A duplicated logical receipt after an explicit corruption fixture
violates intended idempotence. Current APIs should consistently refuse, not count or
mutate such records. This review does not claim normal writes can produce corruption.

Require shared validation of the whole bounded target set before summary/page
filtering and before writes. ID collision lookup must include byte-equivalent BLOB
keys in the same source even when attached to a different fact. Bind normal values;
never interpolate caller names into SQL or normalize stored malformed rows.
Maintain indexed key constraints,4097 sentinel bound and snapshot/IMMEDIATE locking.
Preserve revocation of valid expired/archived/retired facts by checking stored version
without granting live-read eligibility. Do not make damaged unrelated facts a global
service outage. Stable pagination hashes and ordinary output must match baseline.

Accepted tests preserve original75/71 assertions, all source permissions, cleanup
and native gates. New scenarios retain real commands/raw streams and named test-only
SQL mutation plus restoration; malformed stored inputs are not fuzzed user secrets.
No new dependency, service, schema, public release or local-owner task is required.
Outcome still needs a separate code and actual-artifact review after implementation.

Primary references checked: https://www.sqlite.org/datatype3.html (storage classes,
TEXT affinity, comparisons) and https://www.sqlite.org/lang_transaction.html (read
snapshots and IMMEDIATE transaction). A full hostile-schema audit and real external
client/model evidence remain outside this scope. No known plan blocker remains.
