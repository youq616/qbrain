# N47N — Search query / option boundary

Status: approved for implementation, 2026-09-18. Base main b530f361dc9c36cf23127cc2f3c584f3215fb890.
Owner instruction: continue development, then conduct a separate self-review.
Reviewer identity must remain coordinator self-review, not a separate agent.

## Scope and syntax

Only the search CLI adapter and a pure header-only argument parser change.
No storage, retrieval ranking, source policy, other CLI handler, or model policy changes.
Retain ordinary positional words and interspersed known options. Add:
- `--`: ends option parsing; every following token is query data.
- `--query TEXT` / `--query=TEXT`: one explicit query, including option-shaped text.
- `--brain=VALUE`, `--limit=VALUE`, `--mode=VALUE`: unambiguous attached values.
For brain/limit/mode, a separated value beginning `--` is rejected as missing;
use attached form for an option-shaped value. --query consumes its next token
as data even when it is `--`. Mixed explicit/positional queries, duplicate actual
options, unknown long options, and missing values fail before opening a brain.
Single-hyphen tokens remain positional. Positional words retain old joining and
outer trimming. Explicit queries preserve bytes; empty/whitespace-only queries
return the existing query-required exit 1 before opening a brain. Parser errors
use exit 2 on stderr. Actual empty brain names remain invalid.

## Acceptance

1. Original failing option-prefix query works through either explicit syntax;
   '--brain', '--json', '--mode', '--rerank-llm' query data cannot become settings.
2. Verify parsed query plus every option directly, including tokenmax/no-vector;
   no fake network endpoint or real provider credential required.
3. Real CLI/MCP search parity on one-source synthetic fixtures; prove nonempty
   expected hits (not equal empty arrays), source/brain isolation and data hashes.
4. Ordinary positional output/exit compatibility against the baseline on identical
   state; cover limit, mode, JSON/text, CJK and explicit rerank flags.
5. Rejection precedes brain creation; explicit/environment/file/default brain
   precedence retained. Search remains locally unscoped; MCP source policy unchanged.
6. Pure parser tests, real-process regression, original N47M/CJK/retrieval tests;
   full N42/N44 native gates, source identity and raw artifact review before merge.
7. Final separate coordinator review includes extra tests and baseline rejection.

## Boundaries and rollback

Python/CMake are test tooling only; Windows product remains native C++20.
Tests use temporary isolated SQLite and scrub provider/Qbrain environment.
No global CLI rewrite, new source option, migration, Hook defaults, provider
permission or release. `--no-vector` still only disables vector requests: it
is not a blanket network-off switch for explicitly requested reranking.
Rollback source commit, no data migration. Keep candidate draft until gates finish.
