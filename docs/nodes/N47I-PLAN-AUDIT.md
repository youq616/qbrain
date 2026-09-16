# N47I plan review

Reviewer: ChatGPT, separate owner-authorized engineering self-review.
Verdict: PASS for scoped implementation; runtime/outcome acceptance pending.

The observed gap is at raw JSON entry points. Inspecting a parsed map cannot
recover overwritten duplicates, so rejection must precede dispatch and capture.
Tracking one set per object (not one global set) preserves sibling/array semantics;
escaped key equality must be tested after JSON decoding. Returning false from a
parser callback is not a safe rejection mechanism because it may discard data.

Keep error messages fixed and non-sensitive; ambiguous request id must not be
echoed from one arbitrarily chosen member. Byte and depth limits prevent adversarial
bookkeeping from growing without bounds, but must fit existing valid event/MCP
shapes. Test both sides of every boundary using the bundled version rather than
assuming current online examples have identical behavior.

Preserve the historical batch payload error contract. Public memory permissions
and Hook enablement must remain outside parsing decisions. Rejected events should
not open/migrate/write a brain; a diagnostic about rejection is not a memory record.
Do not retrofit stored user evidence or implicitly canonicalize source IDs, keys,
Unicode normalization or facts. No new schema, provider or installer configuration.

P0/P1 design blockers: none identified with fixed error/no-dispatch semantics.
Primary risks: sibling keys falsely rejected, array depth bookkeeping, exception
swallowed as success, rejected notification still dispatched, and Hook failure
writing an event. All require actual negative tests plus unchanged valid fixtures.
The planned generated oracle is supplemental engineering checking, not external
review or proof that all possible parser errors are absent.
