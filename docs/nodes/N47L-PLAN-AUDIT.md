# N47L plan review

Reviewer: ChatGPT, separate owner-authorized engineering self-review.
Verdict: PASS for the stated implementation scope; no runtime acceptance yet.

The feature is explicitly requested per-call rather than silently changing literal
query semantics. It adds task-oriented multi-keyword retrieval without claiming
semantic understanding. Query text stays bound parameters; only the closed mode
enum selects a fixed SQL connective. Entire-query validation precedes splitting
so sensitive-input checks cannot be bypassed by separating a pattern into tokens.

All terms must match one anchor, never separate facts combined into a new claim.
No filtering of required counter-evidence by terms. Full neighborhood size and
single-snapshot semantics remain inherited and need actual regression coverage.
The8-term and1024-byte bounds include duplicates and source whitespace; do not
silently drop extra terms or truncate queries. Unicode whitespace/case limitations
must be documented, not presented as language-aware segmentation.

No changes to Hook defaults, schema, permissions, confirmation counters or model
calls. Wrong-view match parameters must be rejected by CLI/MCP routing, not ignored.
Existing literal outputs are an exact compatibility oracle; new set results need
an independent expected conjunction/disjunction oracle and negative paths.
Both MSVC closures, native group registration and full report gates are required.

No P0/P1 design blocker identified with these constraints. Main risks: accidental
OR for all_terms, applying the query to counterclaims, split validation bypass,
new metadata breaking default byte compatibility, and silently accepting match on
unrelated routes. Each has a required falsifiable test. Final outcome approval is
separate and cannot reuse this design PASS as execution evidence.

## September 17 repair plan review

Reviewer: actual independent subagent `/root/recall_interface_review`, with
separate report-gate inspection by its `report_gate_review` subagent. Decision:
PASS for the bounded compatibility repair before implementation; runtime/outcome
review remains separate. The reviewer reproduced the `--query --match --brain
probe` rejection against the original candidate executable and confirmed that
`with_brain` consumes only brain selection, so passing the parsed brain option
preserves its normal fallback behavior. Explicit empty and missing values must
retain their rejection behavior, and duplicate named options must still fail.

The original process report validator also accepted duplicated/replaced command
histories because it checked only length and self-reported exits. Fixed semantic
schedule/exit expectations and mutation tests are required before the new report
can support stage acceptance. This does not claim the original real CI skipped
those commands; independent CI inspection confirmed that it did execute them.
