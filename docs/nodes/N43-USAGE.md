# N43 session memory / N44A native transport

Development branch: `optimization/n43-memory-cycle`, stacked on N42. Native validation is required before acceptance; see N43-HARD-AUDIT.md and the associated Actions run. This is not the completed N43–N46 roadmap or an installer release.

## What is implemented

Two operations, `memory_read` (read) and `memory_write` (write), share the source resolver and central capability checks. The historical 108-operation N31 inventory is still checked unchanged; these two additions are separately tested. New code lives in `memory/session_memory` and `ops/memory_ops`, rather than enlarging the monolithic handler implementation.

`memory capture` accepts one UTF-8 JSON object on stdin (maximum 256 KiB). Its messages must carry explicit roles. Example synthetic input:

```json
{"session_id":"demo-session","fragment_id":"turn-0001","messages":[{"role":"user","content":"我偏好不用 Docker，使用 Windows 11。"},{"role":"assistant","content":"This response is not evidence of a user preference."}]}
```

Fields: session_id and fragment_id (nonempty, at most 128 UTF-8 bytes), messages (1–256), optional expires_at (Unix seconds; zero means no expiry). Each message has only role and content. Valid roles: user, assistant, system, tool, unknown. Session/fragment IDs must be stable on retry and distinct for different portions of the same conversation. A changed payload with the same source/session/fragment is a conflict, not an overwrite. Opaque event IDs are SHA-256 of the source, identities and canonical content hash, not second-resolution time.

## CLI and PowerShell

Explicit local manual archive, without changing the automatic-write policy:

```powershell
# $payload is the JSON string above. The bridge sends bytes directly, avoiding
# Windows PowerShell's legacy native-pipeline encoding.
$r = & .\scripts\Invoke-QbrainJson.ps1 -FilePath .\build\cl\qbrain.exe -ArgumentList @('memory','capture','--manual','--brain','memory-demo') -InputJson $payload
if ($r.ExitCode -ne 0) { throw ($r.Stderr + $r.Stdout) }
$event = ($r.Stdout | ConvertFrom-Json).event_id
& .\build\cl\qbrain.exe memory extract --brain memory-demo --event $event --method local
& .\build\cl\qbrain.exe memory read --brain memory-demo --query '不用 Docker' --max-bytes 8192
& .\build\cl\qbrain.exe memory status --brain memory-demo --event $event
& .\build\cl\qbrain.exe memory forget --brain memory-demo --event $event
```

Initialize a disposable brain with `qbrain init --brain memory-demo` before trying the example. Do not test with a real memory database. Existing source selection remains `--source`; omission means `default`. Read limit is 1–50 and response budget is 512–32768 UTF-8 bytes. Complete quotes are skipped, never cut into a different proposition. Queries use literal substring matching (ASCII case-folding plus exact Unicode); this module is not a semantic/ANN search engine. It examines at most 200 candidate rows and reuses evidence hashing only within the same SQLite statement, not across calls.

Without `--manual`, capture obeys persistent `memory.writeback=off|salient|all` (default/config behavior is inherited). Off means no archive, optional-schema creation or provider call. The existing local `qbrain config set memory.writeback salient --brain memory-demo` command can opt a disposable brain in. `salient` does **not** filter archival message content: it restricts extraction categories. `all` additionally permits explicit general-fact statements. Manual archive is not external-model consent.

Local extraction uses documented explicit English/Chinese sentence-prefix markers, not general semantic understanding. It preserves each complete user message and labels its category. Questions, quotations and hypothetical text can still fool this small classifier; results are caller-attested statements, not verified facts. No claim of semantic extraction accuracy is made. Legacy `session-capture` stores speaker-unattributed input as `unknown`, so it cannot invent user statements from mixed transcripts. Repeated raw content no longer overwrites another capture occurring in the same second.

## Model extraction and usage

`memory extract --method model` requires the separate persistent setting `memory.external_extraction=allow`, even after manual capture. The operator must configure the existing chat provider explicitly. No key yields `archived` / `model_unconfigured`, without a fake successful extraction. No extraction is automatically invoked by capture. The caller/host must separately request it; a full automatic Agent lifecycle is not part of N44A.

Only user-role messages are sent to the model. Candidate output must contain at most 32 objects with exactly `message_index`, `category`, `quote`; the quote must equal the **whole original user message**. Substring matches that discard negation, assistant messages, extra fields and invalid categories reject the entire batch. The role is attested by the authorized caller, not cryptographically authenticated to a human. Untrusted recall text must never be executed as instructions.

`memory status` exposes recent attempts. Reported input/output token counts are preserved when available; missing or crashed-request usage is null/unknown, not zero. Local extraction uses no provider. Provider-attempt count means the attempt was initiated; a crash before actual send cannot be distinguished from a billable abandoned call. Model/provider pricing, end-to-end agent token savings and embedding/rerank costs are **not** included in this partial ledger. No live-provider integration or extraction quality benchmark has been run in this stage.

## Lifecycle, isolation and limits

An optional SQLite module with its own version 1 is initialized transactionally on the first permitted capture, following a unique on-disk backup. The core schema remains unchanged. PostgreSQL memory operations fail explicitly rather than pretending schema/SQL compatibility. No user database has been migrated during development.

An extraction lease keeps concurrent or late workers from publishing duplicate/stale output. Failure records stay retryable; an abandoned worker can be retried after its 90-second lease expires. SQLite startup/transaction contention can fail explicitly and callers must retry boundedly. Tests count observed retries rather than hiding them. After a provider returns, the lease, evidence hash/deletion, expiry and policy are checked again. A failed publication rolls back as a whole. Different, even conflicting, user statements are retained with evidence; semantic contradiction resolution and supersession are not implemented.

`memory_read` suppresses items whose parent is missing, edited, deleted or hash-corrupt, and expired items. Expiry governs extracted recall; it is not an archive-retention or secure-erasure policy. Raw session archives are normal source-scoped pages and can still be accessed by authorized general page/search operations. `forget` removes the items and the unchanged archive (including a soft-deleted archive), cancels the lease and retains an identity tombstone to block replay. Edited/reassigned pages are not destroyed. This does not securely erase SQLite WAL, system backups, previously returned context or already-sent provider requests. The first module backup can contain pre-existing brain data and should be protected like the database.

Credential-pattern screening rejects obvious key/password assignments before archival/external extraction. It is deliberately conservative, incomplete and may have false positives. It is not comprehensive secret/PII detection, encryption or a new filesystem ownership model. Existing source-level ACL remains the trust boundary. No cross-source global facts are populated. HTTP transport/capability paths reuse the registry checks, but native stdio—not complete HTTP deployment—was exercised by the new process suite.

N44A supplies `wmain`, UTF-16/UTF-8 conversion with exact buffer bounds, a Unicode data root, byte-oriented stdin/stdout and the PowerShell 5.1/7 process bridge. It does **not** install Agent hooks, modify host configurations, prove context injection, or claim all legacy filesystem operations are Unicode-safe. N44 host lifecycle, N45 L0/L1 semantic summaries and N46 full quality/cost baselines remain open.
