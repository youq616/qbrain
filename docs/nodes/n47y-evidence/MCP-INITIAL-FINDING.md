# Actual MCP failure and repair scope

2026-09-20. Separate coordinator review of the open N47Y module, not a subagent.
The exact downloaded39357 portable executable (SHA2565310a5016034af11bf7571384c3bb0226ca66085bb60ab9154a740989b5e1780)
was run with ordinary public-CLI setup and an authorized persistent MCP server.
A valid request with view=usage_receipts, receipt_state=all, limit=1 returned:

{"error":{"code":"invalid_argument","field":"receipt_state","message":"unexpected argument"}}

The public tools/list advertises receipt_state and snapshot as strings, but the
separate MCP typed gate has neither entry. The first exploratory test failed on
a corruption-page request for the same reason; the final supplemental test now
checks ordinary positive filtering before any corruption and reproduces this
failure after3 passing controls. These are product-route failures, not a test
fixture excuse. No user database or model was involved.

The approved completion plan precedes the two-entry String allowlist repair.
Existing type/unknown-field/source/permission and route-local validation remain.
The repaired local GCC product passed72 supplemental checks in normal/-O modes,
including seven combined scope/ID type mutations over five MCP execution paths,
three competing-writer schedules, full page continuation, eight invalid requests
and revoke write-ABORT recovery. The original123 integrity/156-command suite and
four focused core groups were rerun without changes and passed locally.

Both final Windows/Linux CI and original full60 native gates still must pass at
the repaired commit before final acceptance. Earlier green39357 cannot certify
this repair. The original two receipt headers remain byte-identical to39357;
this continuation additionally changes only src/qbrain/mcp/server.cpp in product.
