# N48E final review — complete OpenCode configuration lifecycle

2026-09-22, Asia/Seoul. **PASS for the approved source integration and pinned
OpenCode 1.18.31 account-free loading/connection scope. No known unresolved blocking
finding remains in those scopes.** Not a zero-defect, native-V2-engine, model-use,
PG, signing or stable-release certificate. Reviewer: coordinating ChatGPT, separate
engineering self-review expressly authorized by the current user; not a subagent
or independent third party.

## Fixed objects and approval order

Base main: ce2e26201fcdf977a507f895c081ab09f83359b8.
Pre-implementation plan and embedded separate plan review: e679a0af23c63e47879c48b383500c7731e6a229.
Original product/native tests: e419acf60375e1a7a0794375c713f759b776aa0b,
tree4cb6e97c92c6b9cdb8ee01d89cdb54d8b0958225.
Accepted integrated source and host-review code: 206d04eb4a04588007224cc98d56909b0b52a965,
tree3de27b2ef0b5f9b408e6e31d861f7507de683fcc.

The original approved plan is retained unchanged in n48e-evidence/APPROVED-PLAN.md.
The e419-to-206d changes add only host-review tooling/workflow/notes: product headers,
main.cpp and original tests are identical. The later Windows build is a different
EXE, so host evidence still binds its explicitly tested e419 executable.

The preceding continuation completed native and host testing but its upload of
check_host_records.py was blocked. It stopped repository writes; its local audit
was not a merge. The current continuation retried that identical verified script
through the same authorized create_blob action once and succeeded. No alternate
write route was used. This review and actual merge readback complete delivery;
the final merged identity is recorded in PR46, not substituted for a build source.

## Approved criteria mapped to evidence

| Gate | Implementation and observed result |
| --- | --- |
| Complete lifecycle integration | Native preview/install/status/audit/uninstall/recover/reconcile dispatched before normal brain setup. Only nine lines added to inherited main.cpp. Existing N48D, root CMake, large CLI, database, Hook, bridge and permissions unchanged. |
| Explicit authority and safe defaults | Preview fingerprints precede mutations; source-owned tests exercise generated MCP sessions with write denial, explicit enablement and later denial. Preview does not grant write access. No implicit collection or model requests. |
| Preserve unrelated configuration | Bounded unique-key JSONC parsing and original byte spans. Reconciliation verifies the exact owned definition, removes only that member and adopts remaining bytes as the uninstall baseline. Unknown edits, changed owned settings and stale approval refuse. |
| Recover without arbitrary overwrite | State/journal consistency, known staged images, cooperating lock and per-write rechecks. Direct tests inject interruptions and conflicts after earlier writes. Unknown stages remain untouched; per-file atomicity is not a multi-file atomic transaction. |
| Actual native platforms | Windows original60 plus four standalone lifecycle targets; Linux six original core/batch targets plus four standalone targets. All three lifecycle process suites in normal/-O, N48D and fourteen inherited process suites pass. |
| Version-pinned real host | Official OpenCode1.18.31 on both platforms loads the generated entry and reports Qbrain connected. Exact schema-only insertion, drift refusal, reconciliation, permissions updates and uninstall are recorded. No account, model prompt, business tool call or user configuration supplied. |
| Independent outcome verification | Exact archives/source trees/component hashes and original report validators replayed, plus separately written host-record checker with17 rejected mutations. New six-scenario lifecycle sequences pass in both Python modes. |

## Exact native and host evidence

All runs are fixed push/attempt1:
- Original native35612180651: Windows106373780502, Linux106373780819.
- Final integrated native35666915946: Windows106558368876, Linux106558369367.
- Host review35666915907: Windows106554609371, Linux106554609126.
The final native and host jobs and every required step were reread in this continuation.

Six original downloaded archives were rechecked for metadata pins, size, SHA256,
CRC, path/mode safety and source markers. Original canonical source:1283 files,
e419 tree; Windows1269 exact LF-to-CRLF conversions. Integrated source:1288 files,
206d tree; Windows1274 exact conversions. No other normalization accepted.

| Archive | ID | Bytes | SHA256 |
| --- | --- | ---: | --- |
| Original Linux |10644942504|18781884|346c5f3560fce9c2762c367cde1b702010dd3953b3a5bee1ef23c8866a3ef18d|
| Original Windows |10645630760|17820156|9a0f9ee5965ff245b46b2041a5c36d2836fbc2dbc72a310993ff33d5b605accd|
| Final Linux |10669821875|18791748|1dcc64adbd23b12dcd997b8cb8488d7a720c77612002adc25bf414f26184748d|
| Final Windows |10670362885|17830794|ebf92432f581a1bf3c9f96a8f08f1e539c59fc3d7f27dab3a02c42352f5535a1|
| Host Linux |10669073616|12432718|f589c4801439294d1e6b14102a3cc3b1acd2421ec96ef11ab593d38eb9c5ddf8|
| Host Windows |10669593188|12471316|7b28185c8324796659461f7e331d389f46a4ade1c447fd82d6fcad8ef8d69f96|

Actual Linux EXE c5844eef61407912f4b2113dbd18a94a5a00a2f4d206a9e437061f5e44aeb7da
is identical in both native archives. Actual host-tested Windows e419 EXE is
4a90b7c50df446ba354691758a53fc8164fbe10fbf7d0fbb9e26f679b43232bf;
final206d Windows EXE is44ad56d777bbf5e1abf561dd7e0b90d9952856dbf85107b335b2f5b3e1e29f74.
No compiler reproducibility or new host session on the later Windows EXE is claimed.

Per Python mode: installation68 Windows/70 Linux, audit93/96, reconciliation133
checks/164 calls. Direct assertions: config1162/1164, audit486/529, reconcile1345
and write-races164. Platform differences are explicit, not discarded assertions.
All24 native lifecycle reports were revalidated with their exact test bytes and
12/14/16 original negative cases. All16 lifecycle-driver and18 retained-driver
step hashes/exits matched for each original/final platform archive.

Original batch89/165/495, integrity123/156/468, usage75 and pages71/111/333 were
replayed, including raw streams. Persistent MCP72 and semantic facts34/multiterm112/
Hook52/lifecycle40 were verified with their own validators; named60/search226 and
memory44/MCP17 logs checked. Context65 has summary evidence, not individual raw
command bodies. N48D172/96 with14 mutations passed against the combined binary.
Windows BUILD_OK and all60 registered groups were parsed from the original logs.
PostgreSQL is still SKIP-PG. Normal and optimized readback outputs are identical.

## Real-host findings retained, not reclassified as full V2 success

The host writes a missing $schema annotation. The first test's assumption of no
file changes failed. Final records require the exact documented annotation-only
insertion, verify Qbrain reports drift and refuses ordinary uninstall, then use
explicit reconciliation. Other changes would fail; no automatic trust was added.
See HOST-SCHEMA-FINDING.md and the retained upstream blob references.

V1 compatibility loading omits this module's V2 startup/catalog timeout object.
Both formats can connect, but native_v2_engine remains NOT_RUN and
v2_on_v1_timeout_preserved remains false. Use format v1 for the tested1.18.31 host.
See V1-V2-COMPATIBILITY-LIMIT.md. Current V1/V2 official documentation was checked
again; it is not substituted for the pinned binary observation:
https://opencode.ai/docs/mcp-servers/ and https://opencode.ai/v2/docs/mcp-servers .

Each host report contains75 checks and63 records:36 Qbrain commands,25 host commands
and2 exact before/after file observations;10 connected outcomes. The independent
checker verifies ordered approvals, resolved definitions, permissions, V1 timeout,
V2 omission and uninstall absence. Seventeen mutations reject normally and with-O.
Neither this checker nor this continuation reruns OpenCode or a model locally.

## Additional independent work in this continuation

The downloaded Linux binary ran all four existing direct targets and the three
original lifecycle process suites again (70/96/133); their validators and negatives
passed. Separately authored review_lifecycle_sequences.py runs six combinations
of V1/V2 and JSON/JSONC/Unicode/BOM/newlines, each through approval, installation,
two external edits, reconciliation, explicit permission reset, audit and uninstall.
Each Python mode executes114 commands and133 assertions. Independent expected
server definitions and unrelated semantics agree; cross-project, cross-home and
changed-access approvals refuse without writes; changed owned definitions refuse;
stale reconciliation refuses; fresh reconciliation becomes an exact no-op.
Adopted comments/BOM and baseline bytes survive uninstall. Only synthetic project
files are edited; no host, database or model call is involved. The fixture parser
accepts only its known comment token and does not import production JSONC code.

The earlier four-target ASan/UBSan evidence is retained in the supplied local audit;
it was not rerun or represented as a new sanitizer build here. No new product build
or local Windows execution occurred. An initial local archive adapter expected the
wrong source-archive filename; after inspecting actual members it was corrected.
A streaming orchestration interface was unavailable, so the tests were executed
as separate completed commands instead. Neither was a product-test relaxation.

## Security, delivery and remaining limits

State/journal before-images may contain private configuration: they are not
sanitized telemetry. Read-only audit does not inspect global/remote merged config
or prove executable authenticity. Cooperating locks, identity checks and atomic
single-file replacement do not eliminate hostile-admin, last-check-to-rename or
all power-failure races. Recovery rejects unknown data. No implicit permissions,
automatic repair, user-brain deletion or provider calls are introduced.

The final closure changes docs/history and already-executed review materials only.
Verify its diff and merge tree before declaring delivery complete. Historical
local-only/blocked delivery is not retroactively called a successful merge.
No Release/tag is changed; public N47X still lacks these newer source features.
This closes the A/B/C source integration gap, not long-term signed-in memory use,
real model quality/cost, Issue40, PG, signing or stable-v1 acceptance. Raw Actions
archives retain their October5 expiry; derived records are not permanent raw copies.
