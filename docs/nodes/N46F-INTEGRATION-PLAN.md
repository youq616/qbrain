# N46F integration and native completion plan

Status: approved for implementation and measurement; outcome pending.
Reviewer: ChatGPT, owner-authorized engineering self-review, not a third party.

## Inputs and choice

Main baseline: 48a498bbf2ea14b39f1023cd1d67e30fb98848f9.
Remote candidate: 515b80421a708ce80b75bbc3067b1d0e73aec853 (PR #12).
Original local commits: a0adf373c686d1bbc1845d58d84fb6d1b0da372c and
9426692fe40ba41880f9312534f02fde0459cfad, preserved in the verified input bundle.
The source-intake review is on handoff/n46f-offline-source. Its review identified
real gate/fixture/report defects; no original failed result becomes a PASS.

Use ONE literal supplement in the SQLite storage backend, not both the shared
hybrid and backend variants. This leaves PostgreSQL behavior unchanged and keeps
match-centred snippets, source/deletion predicates, FTS-first order and unique page
IDs. Retain the useful local end-to-end cases after their reviewed fixture/count
corrections, and the remote storage/memory/Unicode unit cases. memory_read stays
an evidence-bound contiguous-substring operation, not FTS or semantic search.

## Required acceptance

- Exact 48 registered groups, complete named CJK reports, retained child exit codes
  and same-source/script/EXE bindings. Missing, empty, duplicate, failed or wrongly
  counted evidence must fail packaging. Ordinary ASCII FTS behavior is unchanged.
- Real CLI/MCP CJK tests: source authorization, one/two-character and mixed queries,
  wildcard-looking literals, duplicates, ordering, limits, invalid UTF-8, changes,
  deletion/forgetting, expiry, evidence tampering and no hidden writes/model calls.
- Preserve the existing native HTTP growth ceiling and all timeout/partial-body
  checks. Run 34753274282 failed with process handles 204 -> 222 (+16 ceiling).
  Do not increase the ceiling, lengthen the existing sample grace or retry for green.
- Diagnose app-owned handles and callback-state lifetime separately from process
  handle totals. Keep connection/session owners alive until the request's final
  HANDLE_CLOSING; investigate default cross-session pooling using a compile-time
  test-only control. Any production lifetime/pooling change needs native evidence.
- Retain complete Windows memory/context/embedding/queue/HTTP/PowerShell gates.
  Build/package/publish only a versioned unsigned preview tied to that exact run;
  never substitute the old executable or silently overwrite a Release asset.

## Design assessment

The SQLite-specific choice avoids untested PG policy changes. Binding parameters
and source identity is mandatory; no migration/tokenizer/service is needed. A
request's state and parents must survive its asynchronous cancellation, including
early-error paths. Diagnostic counters must contain no URLs, keys or payload text.
The test-only legacy control must not become a runtime CLI/API bypass. Whole-process
handle counts are observations, not proof that every OS allocation is app-owned.

No open plan blocker identified; implementation/native checks may reveal defects.
No new memory policy, provider consent, schema, cache, paid request or host claim.
The literal lane may scan the selected source: output cap is not a time/RSS bound.
Rollback is a code/test/build revert; no stored-data downgrade. N47 is not marked
implemented by this node. No local compiler/login/source export is required now.

References: Microsoft WinHttpCloseHandle, Concurrency in WinHTTP and option-flags
(DISABLE_GLOBAL_POOLING); SQLite FTS5 unicode61 documentation. Outcome must name
which findings are measured and which historical root causes remain unproven.
