# N47T — Explicit, revocable fact-use receipts

2026-09-19. Status: done for the approved production-source feature scope.
Base main: 9694ffed4ab2c8f73377c469c9031087c830b94d.
Plan approval commit: 45a0dd724270c9bef9910231fd6d4325b151d2e1.
Accepted product/test source: 6e6ca6e8c136fbfd81ee8671c42cfc172a350db7.
Accepted tree: ff094b291f9c5177dc250be6c09ab6acf4b64409.
Native/portable push run: 35440959490, attempt 1.

The original pre-implementation plan is preserved byte-for-byte in
[n47t-evidence/APPROVED-PLAN.md](n47t-evidence/APPROVED-PLAN.md). Its receipt,
revision, source/write, backup, read nonmutation, capacity, cleanup and full
native criteria remain unchanged. The coordinator reviewed it before implementing.

[Outcome review](N47T-HARD-AUDIT.md) maps those criteria to actual execution.
Review is owner-authorized separate engineering self-review, not a subagent or
third party. The closing archive does not change product/test/workflow bytes;
actual merged identity is recorded in PR37 rather than substituted for the
fixed tested source. No new release or real model/client acceptance is included.

This is a slice of the existing broad roadmap's use recording, not automatic
confirmation of truth/consumption, profile construction, ranking or decay. Real
provider/client conditions remain pending; no model result is invented to close
those gates. SQLite receipt tables are a new optional module, not a global schema
version migration. Reverting code leaves inert metadata and pre-module backups.
