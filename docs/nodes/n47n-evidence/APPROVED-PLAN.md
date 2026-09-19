# N47N — Explicit search query boundaries

Status: approved for implementation, 2026-09-18. Base main:
`b530f361dc9c36cf23127cc2f3c584f3215fb890`.
The owner again requests continued development and a separate self-review by
the coordinator after implementation. This node uses that explicit permission;
never describe this as a separate subagent, Claude Code or third-party audit.

## Product scope and grammar

Repair only search's CLI parsing and dispatch. No storage, ranking, MCP operation,
source permission, provider policy, schema, other CLI handler or runtime change.

1. Ordinary positional words and interleaved existing options retain their join
   and trim behavior. Existing flags are --json, --no-vector, --rerank,
   --rerank-llm; value options are --brain, --limit, --mode.
2. Add --query VALUE (exactly one argv value, including option-shaped text or
   the literal --), and --query=VALUE. Explicit query text is not reinterpreted.
   Explicit query and positional query words may not be mixed.
3. At an option position, -- ends option parsing; all subsequent tokens are
   literal query words, including a subsequent --. Options must precede it.
4. Support --brain=VALUE, --limit=VALUE and --mode=VALUE so leading -- in a
   brain identifier can be expressed without a missing-value ambiguity.
   For those three separated value options a following --prefixed token is
   rejected as missing data. --query consumes any following token as data.
5. Reject unknown --options, duplicate options, missing values, mixed query
   forms and empty/whitespace-only queries BEFORE opening a brain. No silent
   partial execution of malformed arguments. Single-dash words remain data.
6. Validate supplied limit as a complete signed decimal int (empty retains the
   old default; valid zero/negative/large int retains the existing 1..100 clamp).
   Mode is balanced/conservative/tokenmax; empty preserves default balanced.
   Invalid numeric/mode inputs are intentionally rejected rather than ignored.
7. Pass only actual parsed brain option to the existing resolver, retaining
   explicit > environment > file > default. No second scan of query/values.
   Existing local search is unscoped across sources; do not invent --source.

## Falsifiable acceptance

- Prefix query, literal --brain/--json/--mode/tokenmax/--rerank-llm/-- and UTF-8
  text survive through real CLI and match MCP on single-source synthetic data.
- Both literal forms, option ordering, error/empty/duplicate/missing cases,
  explicit/environment/file/default brain routing and no stray directories.
- Ordinary successful inputs compare exact exit/stdout/stderr against the main
  product baseline on identical synthetic data; record the exact comparisons.
- Rejected syntax creates no data root, brain database or provider operation.
  Literal query content cannot activate flags or alter mode/brain/limit.
- Keep N47M and older memory/context/fact/recall/MCP/config regressions intact.
  Test a pure parser target plus real processes; run Windows/MSVC and retained
  N42/N44 gates before marking the stage complete or merging.
- A separate outcome review checks diff, builds/tests, adversarial cases and
  source/artifact identity. Record actual evidence and pending gates honestly.

## Plan review before implementation

Reviewer: coordinating ChatGPT in a separate engineering plan-review pass.
Verdict: approved for implementation. The new grammar resolves ambiguous input
without rewriting global helpers. Preserve exact explicit query bytes and
allow the literal -- after --query or after a delimiter. Validate all syntax
before with_brain. Test no-side-effect failures, not only successful searches.
Do not equate --no-vector with no LLM reranking: it disables embeddings only;
this node must not silently change that existing behavior.
No blocking plan finding remains. Native tests and outcome review are not yet
executed and are not waived by this plan approval.

## Security, delivery and rollback

Tests use isolated temporary SQLite roots with provider/QBRAIN env scrubbed;
no real brain, credential, logged-in client or live PostgreSQL is accessed.
Python remains test-only. Headers and tests must build in C++20/MSVC. Keep
existing CI gates and publication guards. No new public Release/tag this stage.
Revert scoped changes to roll back; no data migration. Put required handoff files
in GitHub; delegate no local task unless actual host access is necessary.
