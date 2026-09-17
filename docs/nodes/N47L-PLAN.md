# N47L — explicit multi-term fact recall with complete counter-evidence

Baseline main: d033bdb23ae483a9bc68893ce1bb32c77d76fb28.
Status: approved after N47L-PLAN-AUDIT.md; implementation/outcome pending.
Only Windows-native youq616/qbrain. Owner authorizes separate engineering
self-review, not a fictitious external/subagent approval.

## User-visible slice

Existing public fact recall treats the entire query as one literal substring.
Add optional match=literal|all_terms|any_terms to FactStore::recall, CLI
`fact recall --match ...` and existing MCP memory_read(view=recall). Omission
and explicit literal preserve original results and output bytes. No new MCP tool.
For the explicit term modes, split ONLY ASCII space/tab/CR/LF into 1..8 nonempty
terms. The original query, including whitespace, remains limited to1024 UTF-8
bytes; reject NUL, invalid UTF-8, whitespace-only input and more than8 terms.
Repeated terms count toward this bound. No quote/operator parser, stemming,
synonyms, implicit CJK segmentation, semantic ranking or inference.

Validate the complete query for sensitive material before splitting, and retain
per-term checks. Parameterized SQL combines literal instr(lower(object),lower(?))
predicates using AND for all_terms or OR for any_terms, BEFORE the candidate cap.
SQLite built-in lower is ASCII-only; non-ASCII case folding is not promised.
User text never becomes SQL syntax. Return an explicit match_mode for term modes
without echoing the query; preserve created_at/id ordering and all existing bounds.

Only anchors are matched. Every valid direct explicit counterclaim still joins
its complete matching neighborhood even if it matches none of the terms; archived
counterclaims stay eligible as before. Never merge terms from separate facts to
satisfy all_terms. Preserve source/predicate, retired/expired/forgotten validation,
one SQLite snapshot, call-local evidence budgets and no partial-group output.

## Compatibility and non-goals

MCP accepts match only for view=recall, rejects it on every other read/write view,
and enforces string/enum types. CLI accepts --match only for fact recall and keeps
duplicate-option rejection. Existing Hook term extraction/automatic injection
semantics are unchanged; no installer, model, permission, schema or usage-counter
change. No new live-host task. PostgreSQL remains outside this FactStore module.

## Falsifiable acceptance and delivery

Test old default vs explicit literal byte equality; AND/OR/mixed-language order,
repeated terms and ASCII/non-ASCII whitespace/case behavior; missing/invalid mode,
1/8/9 term and1024/1025-byte boundaries, invalid UTF-8/NUL, whole-input sensitive
rejection before split, literal SQL/wildcard characters, old matching facts behind
100 unrelated facts, no cross-fact conjunction, source/predicate isolation,
archived anchors/counterclaims, expiry/forget/retraction, exact budget truncation,
read-only authorizer and actual two-connection snapshot interleaving.

Add native group60, standalone unit and real CLI/MCP process tests with exact
source/EXE/script-bound reports and negative report checks. Keep all original
recall/Hook/diagnostic/lifecycle/strict-JSON suites and both MSVC object-closure
gates. Wire Windows, Server2022, portable and sanitizer checks and package gates.
Perform a separate outcome review and fault/differential checks; only merge and
promote the exact tested package after current native results. Source-only rollback,
no database downgrade. No claim of automatic semantic memory or whole-project finish.

Primary references consulted September17,2026:
https://www.sqlite.org/lang_corefunc.html (instr/lower)
https://www.sqlite.org/isolation.html (read snapshots)
