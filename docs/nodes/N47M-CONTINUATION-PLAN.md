# N47M continuation — September 18, 2026

Status: approved for this continuation after the coordinator's separate plan review.
Baseline candidate: c510e60ec935dcf756e7e29315908af060be999f.

## Owner authorization and reviewer identity

The owner explicitly requests: “好的，你继续开发，本阶段开发完，请由你自己进行独立审核，确保没问题。”
For this N47M continuation, perform a separate implementation/evidence engineering
self-review by the coordinating ChatGPT. This is not a separately spawned subagent,
Claude Code, third-party certification, or a guarantee of absence of defects.
This direct authorization supersedes the pending separate-subagent gate for this
node only; it does not waive native tests, data integrity, consent, or honest
reporting. Historical audit records remain intact. Other repositories are out of scope.

## Verified starting point

GitHub push run 35290029136 completed with successful Windows and portable jobs.
Its Windows artifact 10525864463 has SHA-256
0659e302577efa4dce19bb554cdd5274170d2261ae6f89c1cc56f460f676b6c3.
The downloaded named-argument report records 60 passed checks, 113 commands,
source c510e60ec935dcf756e7e29315908af060be999f and product SHA-256
677dabb700c244c47e3abf04b0aaf6163fc30cd4bdbeb33b76b268df1f1b9caf.
A green job alone is not the final acceptance decision.

## Remaining implementation and falsifiable acceptance

1. Add this branch to the existing N42/N44 push allowlists. Preserve every
   existing job, command, permission and assertion. Do not publish from CI.
2. Obtain exact current source artifacts and verify source identity. Run both
   full pre-existing workflow matrices, not just the smaller N47M suite.
3. Separately inspect cmd_memory/cmd_context and their diff. Reproduce ordinary
   output compatibility and option-shaped values using an independently written
   probe, including argument-order invariance and manual-consent boundaries.
4. Read back original reports and native logs; cross-check source/EXE identity,
   complete registered unit groups, expected command exits, and package identity.
   Missing/failed/skipped required evidence blocks completion. PostgreSQL without
   a live DSN remains explicitly SKIP-PG, not silently treated as acceptance.
5. Fix any material findings and rerun affected tests. Record the actual reviewer,
   commands, failures and scope in a final outcome document, preserving the
   original checkpoint and evidence limitations.
6. Merge only when the approved scope passes and the current main/head identities
   still match the reviewed candidates. Update current status/ledger accurately.
   A public preview publication is separate from code acceptance and is not
   automatically authorized by a successful CI job.

## Separate plan self-review

The absent branch filters explain why the full gates did not run. A two-line
allowlist change is sufficient; no new dispatch token or workflow privilege is
needed. Product changes remain limited to the two existing named-option handlers.
Additional independent probes must use temporary synthetic SQLite data, scrub
provider credentials, avoid network/model/client use, and never touch real brains.
Do not modify old tests to make them pass, conflate overlapping cases with bug
counts, or attribute earlier tests to the current runtime. No blocking flaw in
this bounded plan was found. Rollback: revert continuation commits; no migration.
