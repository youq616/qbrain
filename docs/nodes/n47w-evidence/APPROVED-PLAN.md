# N47W — Privacy-safe process-bridge phase diagnostics

2026-09-20. Status: approved after the separate plan review.
Base main: a3436c09e1eaed1d1e4eb6dcfaffbe19cc443eca.
Owner requests continued development and coordinator self-review.

## Goal and scope

Make Issue40-class bridge failures diagnosable without recording arguments, paths,
stdin, stdout, stderr or environment values. Issue40's historical root cause is
unknown; adding diagnostics cannot retroactively establish it. Keep that issue open.

Modify only scripts/Invoke-QbrainJson.ps1 among inherited production files.
Expose a bounded versioned JSON diagnostic in Exception.Data[QbrainTransport]
for failures after preflight; optional -IncludeDiagnostics adds Transport to a
successful result. The default successful result retains exactly ExitCode/Stdout/
Stderr. No new log file, global variable/encoding, network call, default option,
C++/schema/installer/Hook behavior or release change. This is not host-use proof.

## Falsifiable acceptance

1. Report only fixed phase/error labels, numeric timings, nullable process exit
   observation and task completion states. Phases distinguish synchronous start,
   input transfer, process exit wait and output drain. Process.Start returning is
   NOT proof that PowerShell/client/engine initialization completed.
2. Preserve timeout messages, the 10000ms default and 100..120000 range; no retry,
   increased limit, infinite wait or process-tree kill. Input wait must consume
   the same remaining elapsed-time budget as process/output waits, not a fresh
   timeout after a slow start. Synchronous OS startup and cleanup remain explicitly
   outside any strict total wall-clock guarantee. Cleanup retains its2000ms bound.
3. Failure diagnostics describe the pre-cleanup observation and contain no exception
   text, paths, command line, content or credentials. Ordinary PowerShell error
   records may still include call-site information; only the diagnostic JSON is
   designed for sharing. Preflight/binder failures need not carry this diagnostic.
4. Execute native PS5.1/7 tests with a separately compiled deterministic C# child:
   exact success/nonzero/Unicode behavior; invalid executable start; blocked stdin;
   live-process timeout; exited parent with inherited-output descendant; cleanup
   and repeated failure; no sensitive-string leakage in diagnostic payloads.
   Do not infer Issue40 reproduction from these intentionally induced failures.
5. Retain original byte transport, installation/consent/fact/promotion, snapshot/
   recovery and full60 native build gates. Test actual new bridge from source,
   source-pin artifacts and inspect original reports/logs. Add an offline strict
   report checker with negative mutations and normal/-O tests.
6. Separate outcome review must inspect API compatibility, metadata privacy,
   timing semantics, task/handle cleanup and actual native evidence. Fix blocking
   findings and rerun the modified source. No merge based solely on a green badge.

## Rollback and limits

Revert the bridge and additive diagnostic tests/docs. No data migration or user
machine action is required. No real model/client, paid provider or PG validation.
Output capture retains its existing memory behavior; this node is not an output
size limiter or hostile executable sandbox. Descendant termination semantics are
unchanged. Parent-process wait and stream completion are deliberately distinct.
Global ledger/tool inventory remains unchanged; record a node delta only.
