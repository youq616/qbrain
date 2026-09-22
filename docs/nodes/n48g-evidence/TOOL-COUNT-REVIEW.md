# Separate outcome review: excluded tool fees do not waive field validation

2026-09-22. Owner-authorized coordinator self-review. An independent public-CLI
reproducer on the lower-bound-fixed binary accepted server_tool_use with known
web_fetch_requests=1 followed by invalid web_search_requests="invalid". The early
exit after deciding to warn about excluded fees skipped the remaining counter.
Actual request, result and binary identity are saved in review-tool-count-before.json.

Approved correction before implementation: visit every allowed tool counter,
collect the exclusion flag, then append a single note after all counters pass.
No extra tool fees are estimated. Two direct and two CLI negative cases preserve
both positive-first and null-first paths; do not weaken previous checks or alter
the original exact arithmetic. This is a validation bug, not a provider charge
observation. Final source must be rebuilt and the complete original gates rerun.
