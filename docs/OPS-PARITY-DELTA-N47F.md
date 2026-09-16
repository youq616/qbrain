# N47F capability delta

Reviewed/tested product: cafb48667177002ae6ea0f1976eea2f388826024.
Required native runs35076641849/35076641751 and pinned sanitizer35077139073 passed.
See N47F-HARD-AUDIT.md and n47f-evidence/SUMMARY.json for original evidence.

Added explicit fact archive/restore with expected_revision and live evidence,
and read-only fact lifecycle / memory_read(view=lifecycle). Archive only changes
per-fact recall policy: no anchor, but mandatory valid direct counter-evidence is
preserved. No retired/expired/forgotten fact resurrection. Optional metadata is
backed up before lazy initialization and cascades without copying quotes.
Age is advisory from valid support creation times, not use or confidence. Invalid
storage types are not coerced into a valid age. No automatic state transitions.

Existing fact truth/retirement statuses, six MCP names, write/source permissions,
client switches and external-provider consent remain. Old versions ignore archive
policy. Archive is not secure deletion or a way to suppress contrary evidence.
Native registry is54 groups; new lifecycle17 scenarios/180 assertions and36 actual
process checks/58 expected exits passed. Real PG DSN remains explicitly skipped.
Automatic semantic consolidation, counters, aging, profiles and million-event
performance are deferred, not claimed as implemented by earlier conversation.
Review is a separate owner-authorized engineering pass, not an outside subagent.
