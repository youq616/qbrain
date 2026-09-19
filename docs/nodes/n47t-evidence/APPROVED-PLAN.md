# N47T — Explicit, revocable fact-use receipts

2026-09-19. Status: approved for implementation after the separate plan review.
Base main: 9694ffed4ab2c8f73377c469c9031087c830b94d.
Owner requests continued development and coordinator self-review. Real provider
and logged-in-client conditions remain absent; this node advances the existing
broad roadmap's use-recording feature instead of inventing external acceptance.

## Product scope

Add `fact report-use` and `fact revoke-use` (strict JSON stdin), and read-only
`fact usage --id ID`. Route these through existing memory_write actions
fact_report_use/fact_revoke_use and memory_read view=usage. No new MCP tool name.
A receipt means only that an authorized caller explicitly reports use, never
verified host consumption, fact truth, or implicit user approval. Hook, search,
read, ranking, decay and profile behavior must not change or generate receipts.

The caller supplies an opaque 64-hex usage_id, fact_id and expected_revision.
Reporting requires the same currently active, supported, unarchived fact revision.
Repeated identical IDs are idempotent; same-source ID collisions with a different
fact/revision reject. Withdrawals retain tombstones so retry cannot resurrect them.
Revocation accepts fact_id/usage_id and can withdraw stale-version or archived
receipts without changing facts. Read reports current-revision and other-revision
counts separately; never include quote/session text in this new receipt table.

## Acceptance gates

1. Lazy optional SQLite module: versioned receipt table with source/fact composite
   foreign key and delete cascade. No global schema migration or changes to legacy
   facts table. First valid write backs up before optional module initialization.
   Reads and rejected preflight writes do not initialize it. Foreign-key setting
   is checked; SQLite-only is explicit, no false PG claim.
2. Revalidate under an existing BEGIN IMMEDIATE write transaction. Unique source/
   usage IDs serialize concurrent duplicates. Limit to4096 stored receipts per
   fact including withdrawn rows; no silent eviction or bounded-dedup expiration.
   Counts distinguish current revision from historical revision; wrong/stale/expired/
   absent/foreign-source/archived report requests reject without a fact mutation.
3. Forgetting the last support deletes its fact and cascades receipts. Multiple
   supports preserve the fact but advance revision; old usage never counts as
   current. Retraction/supersession/archival do not become usage or resurrection.
4. All public routes preserve existing strict parsing, write default-deny, source
   authorization and no remote implicit consent. Unknown/duplicate payload fields,
   bad integer/bool/id/limits reject. Usage output is bounded, metadata-only, and
   always labels origin=caller_reported and host_consumption_verified=false.
5. Add real-process regression using fresh Qbrain build, explicit synthetic CLI
   captures/facts, MCP authorization, duplicate/concurrent/id-collision/revocation,
   read nonmutation, backup identity, schema conflicts/corruption, cap and forget
   cleanup. SQL mutation is confined to named test-only corruption/limit fixtures;
   ordinary product fixtures use public interfaces.
6. Build actual changed C++ on Windows and Linux; retain full60 native groups and
   existing memory/fact/recall/process gates. Add direct native/portable use tests,
   independently rerun black-box negatives and review original artifacts. No merge
   until the fixed candidate and final documentation-only diff are verified.

## Rollback, security and limits

Optional schema requires a pre-module backup; reverting code leaves inert receipt
metadata, not automatic dropping of user data. No release/tag, installer, models,
credentials, external host, defaults or canonical ops inventory change. New writes
use existing authorization; callers can lie about use, and the API cannot certify
external behavior. Count limits are per fact, not a global storage quota. No secure
WAL/backup erasure claim. The current v1 external gates remain unclosed and roadmap
round estimates must not mechanically decrease for this broader feature work.
