# N47S metadata projection correction

Approved addendum: ca10f2ab595fc6f4d58e5291aa3f07791b753af2.
The model plan is now v2 and binds context_projection=opaque-session-ids-v1.
Only model-facing session_id metadata is pseudonymized using the random plan ID;
original packet bytes are retained. User quotations and fact/event/item/source
fields are not rewritten. Context JSON is reserialized, so this is explicitly
not byte-identical raw Hook input. A prior v1 plan must be regenerated, not edited
to appear approved as v2. Original engine and scoring contracts remain unchanged.

Three new methods cover actual nonempty evidence, exact preservation outside
session_id, stable/per-plan pseudonyms, literal user text, malformed session
metadata and unsupported projection/context. The integration now checks all100
actual request bodies for scenario-label leakage after generating real engine
packets. The unmodified43 tests plus two framing methods remain, now48 in total.

Before commit, local normal/-O48methods passed; the exact prior a2fd module fails
the nonempty-label regression with one assertion failure and no test error after
correctly binding both fixture imports. An initial local baseline invocation mixed
old validation with a newly generated plan and errored; that harness invocation
was corrected, not counted as a product regression. Offline projection of the
previous real Windows packets checks100 bodies with no testing case labels and
makes no new network/provider calls. Final candidate CI still required.
