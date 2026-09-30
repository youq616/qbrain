# N48X separate design review

2026-09-30. Reviewer: owner-authorized coordinating engineer self-review, not an
independent agent/non-author. Verdict: PASS to implement the bounded design.
This is not implementation acceptance.

Read exact restored 1559-blob 0e3c tree, AGENTS, the prior coverage probe, all
chat/embed entry returns, rerank's local/callback/native/chat fallback paths,
HTTP Writer ordering and command/validator. No equivalent logical recorder exists.

Chosen design reuses existing HTTP event IDs via its writer; it does not introduce
a second HTTP sender or modify transport, 0e3c provider-state/terminality projection,
pricing or signal behavior. Scalar links avoid duplicate accounting at nested
rerank/chat levels. TLS scope ownership must be checked against the captured
collector; stale session or capacity loss must not silently attribute to a parent.

Require explicit local route marks in original branches, not heuristics from
private errors. API result_ok is only the original bool, not semantic model success;
vector-returning reranker has unknown result_ok and an explicit fallback flag.
A pre-HTTP exception is not a completed failed HTTP request. No allocation or writer
failure in an optional scope may replace a provider return; track loss instead.
Constructors/session activation may fail before invoking the original command.

Risk review: do not acquire HTTP collector mutex from within logical collector
locks; writer callback runs under HTTP lock and may acquire only logical collector.
Do not emit TLS pointer values or environment data. Sealing after detach preserves
pending workers, but cannot certify final process exit/output. Cap and fixed reports
are not a total RSS limit; counters and times may be sensitive. Legacy logs remain
explicitly outside scope. Test lifecycle/rollback is local memory/IO only, unrelated
to the frozen PG migration upload.

Go/no-go: exact native tests and independent incremental review remain open until
actually executed/received; do not relabel old 0e3c tests as this candidate.


## Publication amendment, reviewed before push

To avoid manual retranscription of four long inherited files, the new branch carries
a readable git patch with exact before/after blob IDs in .ci/stage_n48x_runtime.py.
Its prepare job is the only contents-write job, can fast-forward only this new branch
at its expected trigger head, and commits only those four files. It refuses dirty,
mixed or unrelated bytes. All native jobs then checkout the emitted actual commit;
bootstrap trigger SHA is not claimed as the tested source SHA. The complete recoverable
diff and tree are saved. No hidden compile-time patch, protected-branch write, force
push, merge or frozen PG action is involved. Design review accepts this bounded
publication mechanism; the exact local assembled tree must match final remote tree.


## Publication resolution before native qualification

The bootstrap prepare job remained queued. The coordinator therefore published the
four already-tested files directly through GitHub Git objects, verifying the complete
assembled tree against the local index before a normal fast-forward commit. The new
workflow has no prepare/write job: all jobs are contents:read and checkout github.sha.
The earlier bootstrap and its pending job are retained, not claimed successful or
silently cancelled. The exact-source recipe remains only as recovery documentation;
it is not run during compilation. Frozen PR65 and other branches remain unchanged.
