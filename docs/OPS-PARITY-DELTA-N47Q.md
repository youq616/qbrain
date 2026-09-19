# N47Q delta — evaluation tooling, zero new production operations

Accepted2026-09-19 for the fixed11c7da21 evaluation-tool scope. Six new Python
files implement50 synthetic cross-session tasks, context/control packets, private
evaluator keys, strict structured-answer scoring and raw-file readback. No C++,
schema, installer, source permission, default consent or operation count changes.
Canonical ledger and frozen inventory remain untouched; this delta does not
replace their tables or claim added parity.

Real Qbrain processes pass50tasks/520commands for each of two event formats on
each native Windows/Linux CI platform. Event format is not a real host session.
Model answers and host consumption remainNOT_RUN; provider usage remainsnull.
Grounded accuracy and25-answerable-task resolution are distinct; oracle fixtures
are not model results. See [audit](nodes/N47Q-HARD-AUDIT.md) and
[usage](integration/TASK-EVALUATION.zh-CN.md). Existing public package is unchanged.
