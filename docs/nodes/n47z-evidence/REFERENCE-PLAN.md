# Additional N47Z outcome review plan

2026-09-20. Same coordinating assistant, separate engineering review under the
owner's express request. The fixed candidate and original native gates remain
unchanged. Add an independently written reference-model test using only public
CLI setup and a long-lived stdio MCP server. Exercise 24 sequential batches,
including the maximum 32 receipts over 8 facts, report/revoke mixtures of new
and no-op items, shuffled requests, stale approval refusal and fresh no-op replay.
After each mutation compare all selected source receipts, summaries and paging
to a Python reference ledger. Read-only SQL snapshots may verify no mutation but
may not seed or repair data. Save actual requests/responses and any failure.

These local Linux supplemental tests do not replace the completed Windows CI
or claim all concurrent schedules. No new product behavior, Windows code or
API permission is introduced. Do not promise a stable-v1 or real-model result.
