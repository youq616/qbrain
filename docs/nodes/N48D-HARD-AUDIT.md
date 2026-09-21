# N48D outcome review — isolated MCP runtime qualification

2026-09-21 (Asia/Seoul). **PASS for the approved source-module scope. No known
unresolved blocking finding remains in that scope.** This is not a zero-defect,
stable-v1, real-agent/model or PostgreSQL acceptance guarantee.
Reviewer: coordinating ChatGPT, performing a separate owner-authorized engineering
outcome review, not another agent, Claude Code or third-party certification.

## Fixed objects and continuation

Base main88c949bad4ea7e15e204008668fde4fdf85e13d2.
Plan4104dbcc40bde994ca6f931ba151ec56f6e16391; plan review0876ac9c82c0da79eef28e5d697214db439f1a97.
Accepted source **d9cf7111f4b751998cf5a7e1d4a2bd92e747eca7**;
tree **5c5e6949fde975cf461671b9b2aae8234a076dbe**.
Fixed run **35595500574**, push/attempt1, completed/success.
Windows job106319228892; portable106319228573. Every required step was read back.

This final continuation found PR45 already implemented and tested, but still a
draft with outdated description and no final outcome archive. It inspected the
actual diff, approved plan, final code and artifacts; re-executed tests; authored
additional independent edge probes; and closes that module rather than starting
a competing feature. The original plan is retained in n48d-evidence/APPROVED-PLAN.md.
The inherited production diff is only main.cpp dispatch; the two transport/checker
headers and test project are additions. Original registry, CLI handlers, CMake
root/build scripts, database, Hook, installer, permission and ledger bytes are unchanged.

## Approved criteria against code and actual evidence

| Gate | Reviewed behavior and execution |
| --- | --- |
| Explicit target and read-only preview | Preview hashes the selected regular executable, absolute path, timeout and fixed isolation policy. Run rechecks before launch. No default brain setup occurs at this command entry. Changed target bytes/path/timeout and refused links are tested before workspace creation. |
| Isolated runtime lifecycle | Separate temporary HOME/data/cwd and explicit environment; no inherited provider keys or brain override. Fixed read-only serve command. Initialize, initialized notification, tools/list, ping, input closure and clean exit are exercised against actual Qbrain and deterministic peers. |
| Bounded and truthful observations | One protocol budget, 64KiB frame, 256KiB stdout, 64KiB stderr, 16 received messages and 8KiB result bound. Wrong IDs/types, malformed UTF-8/JSON, excessive output, partial EOF and late output fail without leaking peer text. Complete received frames alone increment the counter. |
| Owned process and workspace cleanup | Windows explicit application path, handle allowlist and new Job; process exit plus empty-Job observation. Linux private group and unreaped direct-child identity. Failure retains unverifiable/replaced/busy workspace; sharing-only retries use the same 2000ms cleanup deadline. Real directory-handle refusal/release tests run on Windows. |
| Positive exit requirement | A valid initialization/catalog is insufficient. Nonzero exit, held output, shutdown stall and trailing data remain failures. The final held-pipe case reports protocol_timeout with successful owned cleanup on both platforms in both Python modes. |
| Preserve existing application | Each platform's 14 existing process suites and original source-owned validators pass. Windows original full60 groups and production BUILD_OK are independently parsed; Linux six existing core/batch targets plus the new standalone target pass. |
| Separate audit and correction | Earlier false message count, Windows fixture scheduling, Job and directory-cleanup findings are retained. Final code, not the earlier partially passing candidates, is accepted. Independent cap-boundary probes and sanitizer checks below pass without product changes. |

The result verifies this bounded Qbrain runtime contract. The six-tool catalog
check checks names, basic object schemas and required receipt routes; it is not a
complete JSON Schema validator or a tool-call behavior test. No tools/call, model
request, root listing or actual agent application is used. Server identity text
and a content digest are not a signature or proof that an arbitrary executable is safe.

## Original failures and what the fixes establish

The prior local outcome review recorded a silent peer counted as one received
message before receive completed. The final code increments only after receipt;
standalone and new partial-EOF/zero-output checks verify the corrected observation.
This final pass does not reconstruct an unavailable earlier local binary or claim
a new execution of that historical reproducer.

Initial Windows artifact10635085930 was reread: after24 passing checks the positive
per-byte-sleep peer had delivered only161 bytes, then failed in catalog at the
original2000ms protocol budget. The fixture now sends the same JSON in32-byte
fragments; production timeouts and original172 assertions were not weakened.

Artifact10635417350 was also reread: after127 passing checks, held-pipe shutdown
returned cleanup_incomplete, direct exit0,739 stdout bytes, process cleanup true
and workspace cleanup false. The old report contains no filesystem error number;
we do not retroactively label it a proven sharing violation. Final code observes
Job drain, shares a2000ms process/directory cleanup deadline, retries only explicit
sharing/lock errors with identity checks, and retains failed workspaces on destructor
exit. Six added native Windows checks demonstrate actual sharing refusal, release
and continued refusal at a short deadline. The final four held-pipe reports pass
the expected-failure/cleanup assertions. Neither case proves the cause of Issue40.

## Artifact, source and raw-record readback

Both exact final archives were reused from their mounted downloads and rechecked
against current GitHub artifact IDs, lengths, digests, CRCs and source markers:

| Original artifact | Bytes | SHA256 |
| --- | ---: | --- |
| portable10637150259 |18030542|79e8e602bbe0c6d7a44f1f6918e6e461774fd43fd1f4b4db91d2bffbc46822ba|
| windows10636553631 |17128751|2d934dabf23a29ffec63cbb88d1904d5fa6f46f65c9c116598891dfff76b4a46|

The canonical1256-file source archive reconstructs exactly the accepted Git tree.
Windows membership/modes match;1242 files differ only by exact LF-to-CRLF conversion.
Actual Linux EXE SHA256195237f99010e535a855e0a98adc89f26aa92425e3dafc6258351ef5ea614868;
Windows EXE SHA256c7369d24017afbbb87dc45baffe5be5bf75cc4e89541a778878e40633fa7451e.

Per platform, per Python mode:172 checks,96 commands,40 runtime-result records
including6 successful outcomes;14 report mutations reject. Original validators
were rerun against all four reports and matching EXE/peer/test bytes. Direct tests:
Windows79, Linux76, separate from original Windows60 groups. The original retained
batch89/165/495, integrity123/156/468 and pages71/111/333 raw streams were rechecked;
usage75, persistent-MCP72, facts34, multiterm112, Hook52, lifecycle40, named60,
search226, memory44 and MCP17 reports/logs were checked using their actual formats.
All18 retained-driver step exit codes and log hashes match. Context65 has a summary,
not individually retained raw command streams. Live PG remains SKIP-PG.

Normal and optimized Python readback produce identical per-platform summaries.
During this pass, the supplementary readback script first failed to guard an empty
invalid-argument test vector, then assumed the Linux wording for Windows CTest's
success line. Both evidence-adapter assumptions were corrected to the actual
record formats; product assertions and original files were not changed.

## Additional independent execution in this continuation

A separately authored edge_peer.cpp and review_transport_edges.py exercise25
edge scenarios plus path-approval/link checks against the exact downloaded Linux
product:54 commands and191 assertions pass in each of normal and optimized Python.
Exact16-message,65536-byte frame,262144-byte stdout and65536-byte stderr bounds
succeed; crossing the limits rejects. Escaped duplicate keys, scalar/null/negative
IDs, partial tail, server requests and late output reject. A deliberately inherited
FD is absent from the peer, and cleanup of an internal directory symlink preserves
the external synthetic target. Same bytes at a different path do not reuse approval.

The original172-process test and downloaded76-check direct test were rerun locally.
A fresh Clang ASan/UBSan build of the unchanged direct test plus final headers also
passes76 checks with an empty sanitizer error log. Only review fixtures/direct tests
were compiled here; no new local product build or Windows execution is claimed.
The supplementary script/fixture are retained in docs; exact report hashes are in
SUMMARY.json. Repeated assertions are not claimed as hundreds of independent features.

## Interpretation, limits and merge boundary

MCP2024-11-05 is intentionally the accepted legacy contract, not a latest-protocol
claim. Official lifecycle/stdio references were checked at
https://modelcontextprotocol.io/specification/2024-11-05/basic/lifecycle and the
modelcontextprotocol repository's2024-11-05 transports specification. Windows
cleanup semantics were checked against Microsoft TerminateJobObject and
JOBOBJECT_BASIC_ACCOUNTING_INFORMATION documentation. POSIX WNOWAIT preserves a
waitable child; Linux cleanup does not establish every escaped descendant has exited.

The selected binary retains the current user's OS rights. Separate HOME/environment
is not an OS sandbox, network restriction, executable authentication or protection
against a malicious binary/admin. Last-check path/identity races are not eliminated.
The protocol and cleanup waiting budgets do not bound synchronous OS/file/kernel
operations. A cleanup failure may retain temporary files; no arbitrary force-delete
is authorized. Runtime reports omit raw peer text/paths; preview deliberately shows
the approved path and is not a path-sanitized object.

N48A/B/C remain separate unmerged OpenCode work. No actual OpenCode/Claude/Codex
loading, write authorization, model utility/cost, PG or signing acceptance is gained.
Issue40 remains open. Public N47X assets stay unchanged and lack N47Y/N47Z/N48D.
Final closure is restricted to docs/history and already-executed review materials;
compare its diff and reread the actual merged tree. Do not call merge-triggered CI
passed in advance. Actions originals retain their2026-10-05 expiry; Git summaries
and local supplemental records do not mean all native archives are permanent.
