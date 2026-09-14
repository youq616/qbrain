# N47C operation delta

Actual tested/reviewed source: 1311bdd51b779e8da6b6420b62ea3f653edfa27f.
Development run 34854466927 and N42 run 34854466971 passed all required jobs.
See N47C-HARD-AUDIT.md and n47c-evidence/SUMMARY.json for exact evidence.

New FactStore::recall, local `fact recall --query ...`, and existing
`memory_read(view=recall,query=...)` provide literal query-directed fact reads.
Each matching assertion is returned with every valid active direct explicit
contradiction neighbor, including nonmatching counterquotes. Full original quotes,
revisions and provenance remain together; no winner, inference or truth score.
Filters precede the candidate cap. One SQLite snapshot spans the neighborhood;
work or byte limits omit an incomplete group and explicitly mark truncation.
Matching neighbor facts remain independent anchors to retain their other edges.

No schema change, new MCP name, write authority, provider consent, automatic
capture or Hook fact injection. Old memories/facts/conflicts behavior remains.
This is the usable retrieval prerequisite for later opt-in host integration,
not that integration itself. No PostgreSQL equivalent or whole-project parity.

The exact native registry increases from 50 to 51. Recall unit: 15 scenarios/330
assertions on both Windows versions and portable. Real recall CLI/MCP: 44 checks/
71 expected exits on Windows and portable. All old gates remain; real PG DSN is
still skipped. Coordinator review adds Linux sanitizer, independent graph oracle,
two failing mutation probes and 162 original artifact readback checks.
Review is owner-authorized separate engineering self-review, not third-party.
