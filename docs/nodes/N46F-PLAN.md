# N46F — CJK literal recall, with endpoint-specific evidence

Baseline: youq616/qbrain main 48a498bbf2ea14b39f1023cd1d67e30fb98848f9.
Status: done for scoped N46F after N46F-HARD-AUDIT.md; not whole-project or N47 completion.
Tested source c665cb29cb44a6827670b8910b3d6adb568aa2c1; native run 34765651987.
Only Windows-native Qbrain; not N47 and not a change to client credentials.
The final HTTP design is N46F-SHARED-SESSION-PLAN.md; earlier pool-option ideas
are retained as rejected history, not the shipped implementation.

Historical starting point: the owner relayed a local summary, not raw logs.
That summary attributed a Chinese memory_read miss to FTS5. Code review showed
memory_read uses bound instr(lower(quote),lower(query)), not FTS5. Subsequent
source handoff and local reproduction established that the spaced query was
not a contiguous substring. Ordinary page search, not memory_read, needed repair.

Implementation: retain indexed SQLite FTS results first, then fill remaining
slots with literal CJK-containing substring matches against title/body/slug.
Bound query text to 1024 UTF-8 bytes, valid scalar encodings, and result count to
500. Bind all text/source/excluded IDs. Preserve source and live-page filtering,
deduplicate page IDs and use deterministic fallback ordering. Return a bounded
excerpt near the literal match. No provider, schema migration, tokenizer/plugin,
new index/cache, data writes, or PostgreSQL behavior change.

Memory reads remain exact contiguous substring reads: no implicit splitting,
synonym inference or fallback to raw unextracted archives. Clarify this behavior
in the tool description and user docs; regress Chinese literal reads separately.

Acceptance: (1) demonstrate old search miss and working literal memory_read;
(2) test one/two/multiple-character Chinese, traditional Chinese, Japanese,
Korean, supplementary Han and mixed text; (3) FTS hits remain first, fallback
fills even with nonzero FTS hits, no duplicates; (4) wildcard/SQL text stays
literal, ASCII queries retain previous behavior; (5) source/deletion/update
visibility and read-only behavior; (6) actual CLI/MCP tests, including forbidden
sources, unextracted/expired/forgotten/tampered memory and bounded output; (7)
retain all existing Windows suites and require new same-source evidence at the
package gate. Publish a versioned unsigned preview and one local runbook only
when required jobs pass; do not modify existing release assets.

Limitations: result count does not bound total SQLite rows examined. Literal
CJK supplementation can scan pages in the selected source; no latency or ANN
claim. No word segmentation, simplified/traditional conversion or semantic recall.
Codex provider 401 is separate; do not read/change/test real keys.
Rollback is a source revert; stored data needs no downgrade.
