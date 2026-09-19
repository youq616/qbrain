# N47Q separate metric review

2026-09-19. Coordinating ChatGPT, a separate self-review pass, not another agent.

The initial grounded-answer metric can give both a perfect context answer fixture
and an all-unknown no-context fixture 100%: both follow their supplied evidence.
That is not proof they resolved the same number of tasks. Comparing only that
accuracy would misstate the memory contribution. This is an evaluation-semantics
finding, not a production memory defect or a measured model result.

Retain grounded-response accuracy over all50 cases, explicitly name its meaning,
and add answerable_resolution over the same25 known/conflict tasks in both modes.
Missing/wrong values or evidence IDs do not resolve a task. Add one separate
oracle-fixture regression proving equal grounded accuracy but25/25 versus0/25
resolution. Those fixture scores are not actual AI answers. Original23 tests are
unchanged; unit discovery now runs24 tests normally and with Python -O.

No state expectations, task count, provider/host acceptance fields or production
code were weakened. Final source and native evidence must be reverified. A
transcription error in an unreferenced draft test blob was rejected by local blob
comparison; that blob was never put in a tree or committed. The original test
file is retained byte-for-byte and the metric test is a separate short file.
