# N47S — Controlled real-model comparison execution

2026-09-19. Approved for implementation following the separate plan review.
Base main a1557ca26fea534c62ef332429f4c1fd773b1414. N47R has actually shipped;
do not redo its integration. Owner authorizes continued development and separate
coordinator self-review, not fabricated independent agents or provider results.

## Goal

Complete the missing executable link between N47Q packets and actual provider
answers. Prepare a bound 100-request plan offline, execute only after explicit
endpoint/model/request-count approval, and score recorded answers without manual
copying. Planning and execution are separate processes; execution never receives
the evaluator key. Random opaque IDs hide scenario names from the request body.

## Acceptance

1. Validate both complete 50-task packets and their evaluator binding before
   planning. Use identical model/settings, independent one-task requests and
   balanced randomized condition order. Questions, expected answers, output
   truncation and evidence rules remain N47Q. No key or original scenario IDs in
   wire prompts; no shared conversations, tools, retrieval or automatic retries.
2. Default is offline plan only. Execution requires the exact plan digest, explicit
   approved endpoint and request cap. Credentials come from a named environment
   variable, never argv or reports. HTTPS certificate validation and redirect
   refusal are mandatory. Only an explicit loopback test mode allows HTTP, has no
   credentials and always reports test transport, never actual model acceptance.
3. Bound each request, output token setting, response bytes and socket timeout.
   Request count includes failed/ambiguous attempts. Fail fast on transport or
   invalid answers and retain attempted/skipped rows; never silently rerun or
   overwrite old evidence. These are request/token controls, not a dollar cap.
4. Persist exact request and redacted response bytes, hashes, timing, response
   model/request identity and provider token counts when supplied. Redact a echoed
   secret before disk, and reject that response. Unknown usage/cost stays null;
   do not fabricate tokens from text or claim billing/host authenticity.
5. Offline scoring binds the exact plan, packets and original key, replays answer
   validation, preserves all 50 tasks in both denominators and distinguishes
   grounded response from answerable resolution. Simulated transport cannot become
   a real-provider result by switching a reported flag. Partial runs are explicit.
6. Add Windows/Linux CI with original N47Q tests and real loopback HTTP process
   integration, negative redirect/secret/malformed/budget/overwrite cases, and
   source-bound raw evidence. Separately review code, test failures and actual
   artifacts before merging. No paid/live model run without user-supplied approved
   provider credentials and settings; remaining real-model/live-client gate stays
   pending if those external conditions are absent.

## Scope and rollback

Add evaluation tools, tests, usage/one-command instructions and a read-only CI.
No C++/installer/schema/Hook permission, original test, canonical ledger or public
Release change. Python remains test tooling. No real brain or client histories.
The endpoint operator sees the explicitly selected packet content; synthetic fresh
packets are required for blinded experiments. Tool is not a hostile-operator
sandbox and cannot prove provider compliance with session/storage settings.
Rollback: revert additive files; no migration. Usage references official Chat
Completions and Python HTTP documentation, not a claim all vendors support them.
