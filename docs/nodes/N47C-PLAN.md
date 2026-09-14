# N47C — query-based fact recall without hiding recorded disagreement

Baseline: 309d71ab79e8bfb55f8b8161ec0126e80514e965 (delivered N47B).
Status: approved after N47C-PLAN-AUDIT.md. Windows-native youq616/qbrain only.
The owner requests repository-side development and separate coordinating-agent
outcome review. Do not manufacture independent subagents or ask for redundant
local work. Preserve earlier reviews and all original regression gates.

## Actual capability

Add FactStore::recall(query,predicate,limit,max_bytes), CLI `fact recall --query`,
and existing `memory_read(view=recall,query=...)`. This prepares a safe explicit
retrieval path for later automatic recall; it does not modify any Hook or opt-in.
Match a nonempty valid UTF-8 continuous substring of the original fact object,
with SQLite's ASCII-only lower(), no token splitting, synonym inference or FTS.
Reject NUL, control-only/blank and queries over 1024 bytes. Preserve literal `%`,
`_`, quotes, backslashes and spaces; no query concatenation into SQL. Predicate
is an optional exact filter. Exact whole-quote matches precede remaining matches,
then updated_at descending and binary fact_id order. Rank is not truth/confidence.

Only active, source-bound facts with validated complete user quotes are candidates.
Before returning each fact, examine ALL of its explicit contradicts relations
(up to the existing 32 bound). If an active compatible opposing fact still has
valid evidence, OMIT this candidate rather than presenting one side as settled.
Count omitted matching candidates in `conflict_candidates_omitted`; do not expose
opposing text/IDs through this view. Clients inspect both sides using N47B's
view=conflicts. The opposing text need not match the query to cause suppression.
Retraction, supersession, invalidation or forgetting of the opposing support can
make the remaining active claim eligible on a later call. This never revives an
inactive fact or infers that an eligible claim is true or contradiction-free.

Keep the outer SELECT active while loading facts and their opponents to hold one
SQLite snapshot. Caches and evidence budgets are call-local: a writer committed
mid-read is reflected by the next call. No copied future-snapshot evidence, new
storage/index/migration, model call, jobs, capture, permission or MCP tool names.
Use existing limits: 100 matching candidates plus sentinel, 512 evidence checks,
8MiB transcript work, 1..50 results, 512..32768 JSON bytes. Stop at a non-fitting
whole record; never shorten evidence or return a fact whose conflict check was
interrupted. `truncated` and `work_limited` report incomplete traversal. Counts
refer only to inspected matching candidates, not total conflicts in the brain.

## Falsifiable acceptance

- Old binary rejects the new CLI/MCP view; complete quote matching, ASCII case,
  CJK/emoji, literal syntax and query boundaries; no raw/unextracted fallback.
- Conflict suppression works when only one side matches, multiple opponents,
  multiple supports, after retract/supersede/forget, and under tampering/expiry.
- No source leakage, half validation, winner selection or fabricated confidence;
  no implicit initialization, backup, write, jobs, Hook changes or provider use.
- Stable filters/order and exact byte limits; candidate/work exhaustion never
  releases a partly checked fact. Negative exits must be preserved in reports.
- Deterministic two-connection WAL tests: add contradiction / forget evidence
  during active reading; coherent current snapshot, next call observes commit.
- Public CLI/MCP strict fields/types; default read works, write stays denied,
  unchanged six tools, old N47A/N47B and ordinary memory behavior retained.
- Add one native registry group (51 total), standalone production-class tests,
  real process test and source/EXE/test-bound report gate. Keep original full
  Windows and Server2022, fact/conflict/CJK/queue/HTTP/Hook/PowerShell suites.

Outcome review is a separate engineering pass after implementation; CI is not a
subagent. No release/merge until required checks pass. No signed release, PG
parity, semantic memory scoring, natural-language question answering or automatic
fact recall is claimed. Output limits are not total SQL work/latency bounds.
Rollback is a code revert; no stored-data downgrade.

References: https://www.sqlite.org/isolation.html
https://www.sqlite.org/lang_transaction.html
https://www.sqlite.org/lang_corefunc.html (consulted September 14, 2026).
