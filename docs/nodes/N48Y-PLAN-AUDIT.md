# N48Y separate preimplementation review

2026-09-30. Auditor: owner-authorized coordinator self-review, not independent
non-author or Claude certification. Verdict: PASS to implement bounded adapter plan.

Read original Issue2/N44, historical project completion and current master §6,
merged hook/trace/installer, open candidate filenames and official Cursor common,
sessionStart/sessionEnd/beforeSubmitPrompt/afterAgentResponse/preCompact schemas.

Rejected: converting every Cursor event as if Claude; injecting additional_context
at beforeSubmitPrompt despite unsupported official schema; using conversation_id
as a turn ID; loading transcript_path; assuming first root authorizes other roots;
using stop to make infinite followups; equating event replay to actual app consumption.

Chosen: typed allowlisted normalization into existing native pipeline, skip query-time
recall for Cursor, context output only at sessionStart. Exact project identity,
explicit user/assistant roles and generation identity, unchanged storage/consent.
Installer reuses existing ownership transaction rather than another unreviewed writer.
Tests must exercise native child commands through installed definitions, not only
JSON shape. Dependencies on old Bridge/CLI are pinned; modified existing installer
must re-pass its original cases. No raw/private event attributes in metadata.

No discovered active author/PR covers Cursor runtime. Inventories of PR61/62/63/64/65
are disjoint; PR66 is AI/observation/rerank and does not touch these files. No writes
to those branches and no attempt involving the denied PG test. Real host/Windows
acceptance cannot be declared by local Linux results. Pending tests/review block
outcome acceptance, not unrelated authorized coding work.
