# N48K preimplementation review

2026-09-26. Separate coordinator design review: proceed with bounded packaging.
Reuse existing strict ZIP machinery and installer rather than an unreviewed auto
updater. Pin native source to the actual merged main; do not patch PE timestamp,
files or tests after building. Deterministic assembly is not compiler reproducibility.
External package acceptance must follow real extracted-program/installer checks,
not merely internal manifest consistency. Source filenames are allowlisted; secrets,
brain databases, CI raw sessions and developer build directories cannot enter ZIP.
No destructive migration is required. Publish a separate candidate/download, never
silently replace N47X or label stable. Outcome self-review is still required.
