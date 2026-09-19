# N47P addendum — bind planned writes to the actual input snapshots

2026-09-19. Approved before this continuation's implementation by the coordinating
ChatGPT in a separate plan review under the owner's current self-review request.
This is not an independent subagent or third-party review. Existing N47P approved
recovery scope and its original tests remain unchanged.

Review baseline: 3ebecf26946ae6ddd04fb018085ffc023b5fcab0 (tree
9bc61a3270c1159a0140b69d0c3d45cc899e7114), already passes its fixed Windows jobs.
The installer still reads target/MCP/owner input before building changes, while
Change captures a newer Raw(path) value. An external edit during transformation
can become the recorded before value although the planned output was built from
older content; the two later comparisons then fail to detect the lost update.
This is distinct from the explicitly deferred atomic multi-file snapshot problem.

## Approved repair and falsifiable checks

- After recovery and while holding the existing installer lock, capture each of
  the five allowed input text images once. Derive owner validation, parsed target,
  MCP, uninstall config, journal before values and backup from those same images.
- Retain both compare-before-write passes, with the post-init comparison before
  backup creation. Do not let a later snapshot authorize overwriting an edit.
- New tests use an explicit test-only serialization wrapper to schedule real file
  edits after input reading but before Change. Delegate serialization to the
  original PowerShell cmdlet; no product-only test flag or runtime bypass.
- Cover both hosts, existing/absent target and MCP, owned config/owner/bridge, and
  normal installation controls. For an early conflict require rejection, intact
  current images, no backup/journal/new brain. Contrast with the exact prior
  installer from this branch, not a different executable or weakened fixture.
- Run the original 60 recovery cases and original five PowerShell suites unchanged
  on both Windows PowerShell5.1 and PowerShell7, plus fresh full native unit suite.
  Additive test/report validation must identify shell, exact installer/test/EXE
  hashes, fixed source and explicit baseline failure, with no false scope claims.

Plan review: this is a local snapshot-binding correction, not a rewrite, schema
migration, new capture consent, C++ change or release. Defaults and legacy text
journals remain. No new dependency, global config or user-machine access. Revert
only the scoped installer change to roll back. Existing scripts and canonical
ledger stay intact. The additional tests must be run before outcome approval.

Limits: snapshots/comparisons are of decoded text (legacy BOM/encoding preservation
is not added); files are not an atomic filesystem snapshot. External writers may
still race between the final comparison and replacement. Brain initialization is
not rolled back when a later conflict occurs. No authentication against a local
administrator or new signed-in client/PG/model acceptance is claimed.
