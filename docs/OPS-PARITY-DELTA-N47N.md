# N47N operation delta — final c26 acceptance

Accepted 2026-09-19 (Asia/Seoul), fixed candidate c26ec5e512d9ba960b86c9ced5b9b4976b031f2c.
Existing search CLI only; zero new operations, schema or provider permissions.
The pure parser preserves --query/--query= and delimiter-based literal content,
validates syntax before opening a brain, and dispatches only actual option values
and flags. Original ranking, retrieval, MCP/source authorization, provider policy
and all other handlers remain unchanged.

Formerly ignored unknown/duplicate/missing/mixed/empty/malformed inputs are now
intentionally rejected. Ordinary valid input retains 22 verified byte comparisons.
Literal CLI data does not imply exact-substring search or punctuation-only hits.

The later ledger regression invalidated the earlier f2ba closure. Its canonical
104+4 table was restored byte-for-byte and is NOT replaced by this delta or an
archive link. The static checker is supplemental; native N31 remains authoritative.

Fresh c26 N47N/N42/N44/ledger gates, 1,216 original artifact checks, 226/302 native
process evidence, 361 parser checks, generated/sanitized and baseline reviews pass.
The added exact-reader comparison covers 356 synthetic inputs without false
approval. Reviewer: coordinating ChatGPT, owner-authorized separate self-review,
not a third party. No new public Release/tag or local installation.

[Final audit](nodes/N47N-HARD-AUDIT.md) · [Usage](integration/SEARCH-ARGUMENTS.zh-CN.md).
