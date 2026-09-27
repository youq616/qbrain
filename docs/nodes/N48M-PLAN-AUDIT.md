# N48M separate design review

2026-09-27. Reviewer: ChatGPT, owner-authorized coordinator self-review before
implementation, not a subagent or third party. Verdict: PASS for implementation.

Reviewed existing backend backup_to, native CLI dispatch and SQLite API contract.
Existing backup_to is pre-migration infrastructure with overwrite semantics; it
must not be exposed directly as a safe user restore. The new administrative path
uses explicit SQLite handles, never Database::handle() or Brain initialization.

Rejected raw-copy live WAL, checkpointing the source, overwriting a live directory,
trusting a self-edited manifest, serializing reports with user data/path text,
and advertising database-only recovery as a complete brain-directory backup.

P1 data loss is bounded by new-directory creation and no automatic live restore.
P1 inconsistent snapshots is bounded by a pinned read transaction and checking
backup_step()==DONE AND backup_finish()==OK, destination close and PRAGMAs.
P1 unknown provenance is exposed; an external manifest digest is mandatory.
P2 filesystem races are reduced by no-follow path/type checks and exclusive file
creation, but hostile local concurrency is explicitly not a supported boundary.
Permission inheritance and plaintext backups must be disclosed; no automatic
external upload or data access is authorized by the development task.

Scope fits native Windows/C++20. Runtime fixture uses only synthetic data and
requires no user secrets or extra runtime service. Outcome PASS requires actual
fixed-source native results and independent comparison of restored data, not
merely compilation, test counts or consistent hashes.
