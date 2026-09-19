# N47V delta — installation path eligibility

N47V only changes the project installer's path checks among inherited production
files. It retains normal legacy installation IDs and refuses sensitive/unverifiable
directory components. Native metadata handles are read-only and disposed; no flag
changes, ID migration, new MCP operation, schema, consent or Hook behavior.

Original canonical ledger and frozen inventory are unchanged. Refusing unsupported
paths is not full case-sensitive-project support and does not close broader parity.
The accepted product source is192cdec2; supplemental b28a6378 adds boundary tests
only. Original84 checks and supplemental22 checks passed on both native shells,
with all retained installer gates and original60 native groups completed.

[Audit](nodes/N47V-HARD-AUDIT.md) retains the initial failed old Hook timeout and
successful unchanged retry. Issue40 stays open as a non-blocking reliability
observation, not a repaired defect. No Release/tag is changed. Current N47R public
installer is still the prior version; real-client/model/PG/signing gates remain.
