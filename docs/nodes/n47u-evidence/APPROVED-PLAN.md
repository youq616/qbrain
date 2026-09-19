# N47U — Read-only receipt audit pages

2026-09-19. Status: approved after the separate plan review.
Base main: 4ab3fffc6bb9e6359676a7099d9a9323f02de3d9.
Owner requests continued repository development and a separate coordinator review.

## Goal and scope

Make N47T use receipts inspectable: an authorized caller can find a receipt ID,
its bound revision and withdrawal status before choosing an existing revoke-use.
Add `fact usage-list --id ID`, backed by memory_read view=usage_receipts. Do not
add MCP tool names or automatic writes. The result is caller-reported metadata,
not model consumption, truth, user confirmation, ranking or decay.

## Falsifiable acceptance

1. Return metadata-only rows in ascending usage_id order: usage_id, fact_revision,
   reported_at, withdrawn_at, and state=current|historical|withdrawn. Filter by
   --state all|current|historical|withdrawn, default all. Reuse current full fact
   evidence/source eligibility and archive labels; do not expose expired/retired/
   forgotten facts merely because receipts exist. Reads must not initialize or
   change any table, backup, fact, receipt or Hook checkpoint.
2. Limit1..50 and JSON UTF-8 byte budget512..32768, including one CLI newline.
   Never split a row. If even the first remaining row or envelope cannot fit,
   reject rather than return a non-advancing empty page. End pages have no cursor.
3. First page returns a snapshot digest and optional next_after_id. Continuation
   requires both --after-id and --snapshot; the selected last ID must actually
   exist in the filtered set. Bind snapshot to source, fact, revision, archive/
   initialization status, filter and the complete validated receipt set, not to
   page size. Insert/withdrawal/revision changes reject continuation; restart from
   page1. No server lease, persistent cursor state or cross-request held lock.
4. Read/validate at most4097 records for one fact using the inherited4096 cap.
   Corrupt ID/types/revisions/timestamps anywhere in that bounded set reject,
   including rows outside the requested page/filter. Counts cannot become a
   partially valid picture. Reuse existing receipt schema and index, no migration.
5. Strict CLI/MCP argument contracts; existing write-default-deny and source
   resolution stay in force. A cursor is neither authentication nor write consent.
   Unknown/duplicate/missing options, bad integers, wrong cursor/source/fact/filter
   reject. Discovering a receipt does not authorize its withdrawal.
6. Add real-process tests for complete pagination, filters, changed state while
   paging, page-budget progress, archived/expired/forgotten eligibility, per-source
   isolation, schema nonmutation and named test-only corruption/cap fixtures.
   Preserve N47T75 checks and all existing native/process tests. Build changed
   C++ on Windows/Linux, retain full60 Windows groups and4 portable focused groups,
   and inspect exact original artifacts before outcome approval and merge.

## Review, rollback and limits

Same coordinator performs a separate engineering outcome pass under the current
explicit user request; do not call this another agent or third-party review.
A new small header plus existing usage route/CLI/schema documentation and additive
CI/tests are allowed. Original fact store, receipt writes, hooks, installer,
canonical ops inventory, release/tag and provider defaults remain unchanged.
Rollback code leaves N47T data untouched; no new stored schema or required service.

Snapshots detect changed current metadata, not adversarially rolled-back history,
truth or remote use. Maximum4096-row scan per page is intentional bounded work,
not a large-scale-performance claim. SQLite-only; real client/model/PG/fees and
stable-v1 gates remain pending. No user-machine task or credential is required.
