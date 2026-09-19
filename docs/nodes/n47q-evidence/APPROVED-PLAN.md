# N47Q — Task-level cross-session evaluation

2026-09-19. Status: approved for implementation after separate plan review.
Base main: 38b05106ea5843dcf463e2abfb16cce2850c208e.
Owner authorizes continued development and coordinator self-review.

## Goal

Replace vague task-quality claims with a reproducible evaluation tool. Preserve
prior live Claude Server2022/N47D evidence and its Codex authentication blocker;
do not relabel them as current Win11 acceptance. This node develops and validates
the evaluation infrastructure and runs the real Qbrain engine with synthetic
conversations. It does NOT certify a logged-in client or paid model without an
actual new observation. The pending v1 live-use gate remains explicit.

## Deliverables and falsifiable acceptance

1. Fifty named tasks: five synthetic project subjects across preference recall,
   duplicate replay, forgetting, explicit supersession, explicit conflict,
   archive/restore, project isolation, assistant-role exclusion, capture opt-out,
   and insufficient context budget. All task definitions and stable IDs are fixed
   in source. Random answer markers prevent ordinary prompt hints from supplying
   expected answers. Task grouping is disclosed, not fifty independent features.
2. Execute actual subprocess CLI and documented Hook events in isolated temporary
   roots with scrubbed QBRAIN/provider variables. Capture/extract/promote through
   UserPromptSubmit, not fixture SQL. Separate sessions/processes for recall;
   lifecycle changes use explicit supported CLI operations, not inferred semantics.
   Original quotation/event/item identity must survive; no direct DB writes.
3. Record raw synthetic command outputs, bounded reports, exact binary/script/
   corpus identity, task checks and durations. Unknown provider tokens/cost remain
   null. Host/model acceptance stays NOT_RUN. Generate two task packets, with
   actual returned context and without context, and an evaluator-only answer key
   outside their contents. Never put markers in the question itself.
4. Add a strict offline scorer for structured model answers: unique complete task
   coverage, run/packet identity, exact status/value/evidence-ID sets and types.
   Report accuracy for answer content only, not authenticity, general semantics,
   host consumption or cost savings. Missing/failed answers must not disappear
   from the denominator; incomplete evidence must not become a PASS.
5. Unit/negative tests cover wrong/duplicate/missing answers, key contamination,
   truncation vs unknown, absent usage, invalid numeric values/UTF-8/JSON, report
   overwrite refusal, failed subprocesses and deliberately wrong engine outputs.
   Run the fifty real tasks on native Windows with the fixed published c26 EXE
   and a freshly built Linux executable; existing focused unit groups remain.
6. Separate outcome review must inspect implementation and raw artifacts, exercise
   negative cases, retain failures, and update roadmap without treating this
   infrastructure work as real model/client acceptance or automatic countdown.

## Boundaries

Only tools/acceptance, their new tests/workflow and current-stage docs change.
No C++/schema/installer/Hook default/source permission/old Release/canonical ledger
change. Python is evaluation tooling, not a product service dependency. Temporary
synthetic outputs may be archived for CI; do not collect real brains, histories,
credentials or automatically call paid models. Existing public c26 package still
lacks N47P installer repair; this node neither silently patches nor republishes it.
Rollback: revert the additive evaluation files. No migration or user-machine work.
New client/paid-model adapter execution requires separately explicit authorization
and real environment access; offline supplied answers are never authenticated by
this tool. Existing independent-agent requirement is superseded for this node by
the current explicit request for coordinator self-review, with identity disclosed.
