# N47L capability delta

Tested product source `17e9a435f94e45b3ca22d3da062ba4683c135c4b`, tree
`f9d42819772df53dd8c6337c3cb19c8940d7023a`. Final acceptance is recorded in
[nodes/N47L-HARD-AUDIT.md](nodes/N47L-HARD-AUDIT.md) and its source-bound evidence. N44 `35228307025` and N42 `35228306922`
completed successfully, with each full native registry at 60 groups. Seven
original archives passed 1094 fixed identity/readback checks, covering every one
of the 73 manifest members.

Existing `fact recall` and MCP `memory_read(view=recall)` now accept explicit
`literal`, `all_terms` and `any_terms` modes. Omission preserves the original
literal response. Term modes split only ASCII space/tab/CR/LF, with at most eight
terms inside the original 1024-byte UTF-8 query. Full-query validation precedes
splitting. AND applies within one anchor, never across separate facts; fixed SQL
predicates use bound values before the candidate cap. Valid direct counterclaims
remain complete even when archived or not matching the query terms.

The fact CLI consumes its strictly parsed values once, fixing option-shaped
literal queries and ensuring actual brain selection retains the existing
explicit/environment/config fallback. The process report now validates the full
126-command semantic history, complete argv/stdin, dynamic IDs and fixed exit
expectations. The original 81-command argv/order/expected-exit schedule remains; the 45 appended calls
exercise nonempty literal quotes, routing and error paths. The development
package includes the report-validator dependency needed by the copied runner.

This extends existing recall behavior, not the MCP tool-name inventory. No schema,
permission, collection/egress consent, installer default, model call or automatic
Hook matching change is introduced. Prior diagnostic, lifecycle, batch, candidate,
strict-JSON, HTTP, queue and memory capabilities retain their regression gates.

Literal token conjunction/disjunction does not imply Chinese segmentation,
semantic merging, confidence inference, truth adjudication or PG facts/context
parity. [The separately reproduced next-stage issues](nodes/n47l-evidence/NEXT-STAGE.md)
in unchanged memory/context/search parsers remain explicit backlog; no N47L
whole-project completion or universal defect-free claim is made.
