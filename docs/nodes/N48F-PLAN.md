# N48F — Offline normalized usage and exact token cost accounting

2026-09-22. Status: done for the approved source-module scope.
Base main:6c4f779ee752bd4043847eb79a6d1a5e694d024e.
Plan/review:95d11564e865edaf051191a06bb079c4d72b7b80.
Accepted source:5990fbc4146f06ca53b1af32cf1996e2ae53914a.
Accepted tree:43e7bff202da7149761e0123ac9f07e1b8e16687.
Fixed push/attempt1 run:35695173057.

[Original approved plan](n48f-evidence/APPROVED-PLAN.md) is retained byte-for-byte.
[Outcome review](N48F-HARD-AUDIT.md) maps its acceptance criteria to the final code,
actual native evidence and separately executed rational-arithmetic reference tests.
This continuation finished existing PR47, not a competing module. The final merge
identity belongs in PR47 and must not be substituted for the tested binary source.

The module prices explicit caller-normalized disjoint token buckets, including
failed attempts, with checked fixed-point arithmetic and explicit unknowns. It is
not automatic provider telemetry, a verified invoice or actual model savings.
The reviewer is coordinating ChatGPT in a separate owner-authorized engineering
pass, not another agent or third party. No public release or schema migration.
