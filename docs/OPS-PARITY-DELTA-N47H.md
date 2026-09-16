# N47H capability delta

Product80fe1b9d31de6cc41d06be6db0e1035c1a747eb7; native runs35111907426 and
35111907432 passed required gates. See N47H-HARD-AUDIT.md and n47h-evidence.

FactStore::lifecycle_candidates, CLI fact candidates and existing
memory_read(view=lifecycle_candidates) now discover source-scoped metadata and
an explicit N47G batch_payload. archive suggests live unarchived stale support;
restore lists live archived claims. No raw quote copy, implicit application,
new schema, tool name, permission or installation switch. Age is advisory.

Binary fact-ID seek supports continuation past100 inspected rows. A budget-stopped
current row is not consumed; empty pages can continue and an unchanged cursor
requires larger budget or an explicit incomplete stop. One snapshot per call,
not across pages. Apply still revalidates live evidence and expected revisions.

56 native registered groups; new17/647 unit and43/63 real process schedule; all
old gates and Linux ASan+UBSan retained. Separate review:254 artifact checks,
GCC rebuild,141 report/registry tests, model-based46 traversals/695 pages, and
one correctly failing cursor mutation. No new user-host or PG parity claim.
