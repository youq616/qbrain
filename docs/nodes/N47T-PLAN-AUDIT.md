# N47T separate plan review

2026-09-19. Reviewer: coordinating ChatGPT, separately reviewing the above plan
under the owner's explicit self-review instruction. Not a subagent/third party.
Verdict: APPROVED for this narrowly scoped production feature.

This progresses the existing use-recording roadmap while missing provider/client
conditions prevent genuine external-effect acceptance. It does not relabel caller
attestation as a consumed Hook or confirmed truth. Important design constraints:
receipts are revision-bound; read/search cannot write; withdrawal is irreversible
for that receipt ID; expiry and last-support forgetting must suppress/delete it;
permission checks precede module work. Reporting an old or changed claim rejects.

A source-scoped unique ID and IMMEDIATE transaction provide testable idempotence,
not exactly-once remote delivery. Tombstone capacity remains explicit at4096 per
fact; no quiet eviction that breaks retry semantics. Legacy schemas and optional
module backup conventions are preserved. New module/reads must reject wrong version
and malformed metadata rather than publishing invented counts. Read counts are
not a confidence/ranking signal. Model/provider defaults remain unchanged.

Approved tests cover same/different revision, repeated/withdrawn/conflicting ID,
concurrency, source/write/remote gates, readonly schema state, byte bounds and
support revocation. Existing native suites cannot be weakened or replaced by the
new suite. Optional module creation is a separate schema action and a concurrency
race may leave an empty initialized module, but no false receipt or fact mutation.
No known plan blocker remains. Final outcome must separately inspect code/results.

SQLite primary references considered: https://www.sqlite.org/lang_transaction.html
and https://www.sqlite.org/foreignkeys.html . External model/client, general decay,
PG parity and full-project completion remain outside this approval.
