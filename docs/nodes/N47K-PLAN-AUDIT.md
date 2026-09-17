# N47K design review

Reviewer: ChatGPT, owner-authorized separate engineering self-review.
Verdict: PASS for this implementation scope, before production changes.

The command is local-only and requires an explicit absolute installed config.
It cannot take arbitrary checkpoint filenames or open a database. Keeping it out
of MCP avoids giving model tools a new local file-reading surface. Unknown/unsafe
records fail independently without echoing their text or real paths. OS handles
must read only regular bounded files, with static parent/final reparse checks.
Filesystem races and forged local metadata remain explicitly outside authenticity.

Reuse N47J's projection for the canonical record contract but compare the entire
parsed object to it: dropping unknown fields is insufficient to validate an input.
Guard numeric and boolean types separately because JSON numeric equality can treat
2.0 and2 as equal. Strict raw JSON parsing must precede object conversion to catch
duplicate decoded keys. No record should gain a fabricated success/model claim.

Use fixed event order, exact session filtering, no legacy fallback and no writes
or locks during read. A report is per-file observation, not one atomic snapshot.
Current config.enabled and historical trace presence must remain separate. Output
must explicitly say inspection, not PASS or client consumption.

No plan P0/P1 blocker identified. Primary gates: sensitive bytes never echoed,
invalid files not accepted as records, no read-side mutation, correct final-handle
checks, unchanged normal Hook routing, and actual current-source native tests.
This design verdict is not final acceptance; production tests and outcome review
must still be executed. Broader automatic aging, semantic merge and usage scoring
are not claimed by this diagnostic slice.
