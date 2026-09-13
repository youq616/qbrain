# N46F plan engineering review

Reviewer: ChatGPT under the owner's explicit waiver of external-review gates.
This is a separate self-review pass, not independent third-party approval.
Verdict: approved for scoped implementation; native outcome evidence required.

The key correction is endpoint attribution: memory_read already uses literal
substring SQL. Its behavior must not be relaxed into raw-page or cross-source
recall merely to make a mislabeled report green. Supplement only SQLite page
search, preserve existing FTS priority, use bound parameters, and cover literal
metacharacters. Do not silently change the PostgreSQL path or persisted schema.

A scoped linear fallback avoids a new tokenizer and rebuild/migration; its CPU
cost is explicitly not bounded by the result cap. Limit valid CJK query bytes,
result count, duplicate exclusion parameters and snippet size. No hidden retries,
network calls or retrieval-cache persistence. Existing ranked hits retain scores;
new literal matches carry no fabricated BM25 statistic.

Regression gates: old binary reproduction, adversarial/multilingual unit cases,
actual CLI/MCP source and evidence checks, full native workflow, same-source
report/EXE verification and release readback. P1 gates remain until these run.
The user-supplied local summary is not a substitute for raw-log review or a new
Win11/Codex acceptance result. Do not include private marker/login details in git.
