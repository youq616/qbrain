# N49A: combined verified source candidate

Status: approved for implementation by coordinator plan review. No outcome PASS,
merge readiness or release claim. See N49A-PLAN-AUDIT.md.

## Sources and authority

The owner authorized continued development, ordinary repair decisions and GitHub
pushes. AGENTS.md's September 17 independent outcome review remains required.
This stage addresses Issue #2's final integration workflow; it does not close
the real-client, model-quality/cost, PostgreSQL parity, signing or Issue40 gates
listed in docs/COMPLETION-ROADMAP.md.

Create only `integration/n49a-verified-core` from main
`e0a27f829d970c24ed8c566023ada0911c0042b3`. Fresh remote inspection found no
existing N49A branch. Merge exact PR62 `848ef980200b40101a1908fddfc0d829abc77d8d`,
PR64 `d57e6b32398fca4e59d80dcfab7c5af119dde2be`, and PR66
`1132c97fac1964f84eb593e91ace5bc774a3c98f`. PR65
`0e3c12390ee0f7c2bd8ee9881b6630f4346038fd` is already a genuine ancestor of PR66,
so never apply it twice. Preserve original merge ancestry, source bytes and
historical evidence. Pairwise merge-tree checks show no textual conflicts.

PR61 fixed-e0a delivery tooling is not needed and will not be included or
retargeted. PR63, PR67 and PR68 are excluded. Do not copy, transmit, recreate or
run the frozen PG directory-cache test. No main updates, PR merge/ready status,
deployment, credentials, paid provider, real user data or security changes.

## Integration hazards and design

- Query cache hits bypass embed_texts. Preserve that behavior: a miss records
  exactly its actual embed_texts call; a hit does not invent a provider/model
  call, token amount or bill. HTTP associations belong to real nested entries.
- Read the current source ACL and cache toggle on every authorized query. A warm
  vector must not bypass revocation or return cached page evidence.
- Directory preflight must reject malformed schemas and caller transactions
  before provider/content reads; logical observation must not perturb that.
- INSERT RETURNING cursors, rollback and late callback ownership must survive.
- All added runtime behavior is already in existing translation units or
  headers. Verify CMake and direct-MSVC source/object lists have the complete
  combined dependency closure; preserve the original 60-group registration.
- Retain all original tests unchanged. A combined CMake injection includes each
  source candidate's test module once, plus a new cross-module executable. Its
  purpose is executable product integration, not replacement audit evidence.

## Falsifiable acceptance

1. Exact accepted heads and e0a are ancestors of the candidate; the unique
   excluded candidate commits are not (their shared e0a ancestry is expected).
   Record actual merge trees and source-list closure. Source diff has only the
   accepted modules plus N49A tests/docs/CI.
2. New cross tests use actual Brain/registry/context/observer code and synthetic
   data. Cover cold/warm/disabled cache, source and policy changes, live evidence,
   deletion/restoration, move/close/reopen, zero logical and HTTP work on rejected
   admission, malformed schemas with SQLite authorizer proving zero body reads,
   pending INSERT RETURNING preservation, late ownership, nested calls, and
   metadata-only report privacy. Preserve unknown token/cost fields.
3. Fresh combined CMake build runs original portable CTests, every relevant
   accepted module's native/process tests, new cross tests and original normal
   and Python -O context/Hook/memory tests. Logs record actual counts.
4. Windows CI runs CMake original 60 groups and focused tests, real loopback
   HTTP probes, then the unchanged .ci/run_n48i_checks.py 55-step gate using the
   historical N47X comparison binary with its published pinned SHA256. This old
   binary is a comparison fixture only, not certification of the new product.
5. Separate Windows direct-MSVC job builds production and original 60 groups
   from the scripts, then builds/runs the cross test from those production
   objects using a dedicated fresh-output linker. The existing TestSources
   option appends to the canonical main and is not a standalone-main route.
   Both original build scripts stay byte-identical. No stale-object or
   CMake-only success substitutes for this gate.
6. Fresh full-linked ASan/UBSan focused combined checks retain diagnostic logs.
7. Freeze exact source commit/tree, commands and raw local evidence for pre-push
   review. After approval, normal non-force development-branch publication may
   trigger the exact candidate Windows/55-step CI; verify remote SHA/tree and
   track that CI to terminal result. Initial publication does not imply native
   gates already passed. Stage completion requires a separate non-author
   subagent outcome review of the resulting exact tree and actual native
   evidence. Any failure is fixed and independently reviewed again before
   acceptance; the coordinator plan review cannot replace that outcome gate.

## Rollback, budget and limits

The main branch and prior PR heads stay unchanged. Rollback is discarding this
development candidate; no data migration or automatic reindexing is performed.
Preserve cache size/TTL, network budgets, observer bounds, API/ABI and assertions.
Persisted embedding-space identity remains a separate acknowledged gap.
Portable success is supplementary and does not prove Win11/real-client/model
quality or PG behavior. Workspace-only official tools may be installed.
