# N47Q final review — task evaluation, not live-client certification

2026-09-19 (Asia/Seoul). **PASS for the approved evaluation-tooling and synthetic
engine scope. No known unresolved blocking finding remains in that scope.**
Real client consumption, real model answers, quality/cost gains and v1 acceptance
remain unverified. This is not a guarantee of absence of all defects.

Reviewer: coordinating ChatGPT, in a separate engineering self-review explicitly
requested by the owner; not a separate subagent, Claude Code or third party.
Plan commit7e52f0d759f82441c52ef770629e602708a38bb3 preceded implementation.

## Exact review object

- Base main: 38b05106ea5843dcf463e2abfb16cce2850c208e.
- Tested candidate: 11c7da219ee65d6aa387acbad6e07c0fb8acf090.
- Tested tree: b0f6b33b585abaa9a7f15a7dc1fbf3baca893f22.
- Fixed push/attempt1 CI: https://github.com/youq616/qbrain/actions/runs/35419130373.

Only six new evaluation Python files, the new workflow and stage documentation
are added relative to base. No original C++/schema/installer/tests/workflows or
canonical ops ledger are changed. Reconstructed source archive has1061files;
259 inherited runtime/test/script files match the N47P source byte-for-byte.
The evaluation files/workflow match locally tested Git blobs. Existing
inspect_hook_context.py is inherited, not a new file in this node.

## Approved criteria and executed checks

| Criterion | Evidence and result |
| --- | --- |
| Fifty reproducible tasks | Ten named lifecycle/source/budget families across five Chinese project subjects. Random value markers stay outside the question; stable case IDs and corpus hash bind the tool contract. 50/50 passed in each run. |
| Real engine, no fixture SQL | Actual UserPromptSubmit captures/extracts/promotes user text; separate processes and session IDs perform SessionEnd/SessionStart. Explicit public fact operations handle supersession/conflict/archive. Each run has520commands. |
| Evidence preservation | Original object/predicate/source/user status and event/item support IDs match; assistant text, disabled capture, forgotten or archived content do not bypass through raw memories; both sides of explicit conflict remain. |
| Budget and isolation | Long complete quotation yields explicit insufficient-budget state, not false absence. Actual stdout length is checked against trace count and budget. Isolation uses different project directories and brains, while original project data remains. |
| Packet/scorer integrity | Actual returned context and clean no-context packets are separate from the evaluator key. Missing answers remain in50-case denominator. Duplicate IDs, altered questions/identity, malformed fields, wrong evidence IDs and invalid usage reject or score wrong as specified. Unknown usage remainsnull. |
| Honest comparison metrics | Grounded-response accuracy and resolution of the fixed25 answerable tasks are separate. Fixture-perfect no-context abstention is not evidence of memory benefit. All host/model/authenticity flags stayfalse. |
| Tests and adverse inputs | 24 unit methods pass normally and with-O in both CI platforms and locally. Twelve additional mutated copies of actual output are rejected; restored positive control is unchanged. Four original focused CTest groups pass in fresh Linux builds. |
| Separate evidence review | Downloaded original Windows/Linux artifacts, checked SHA/size/CRC/source identity, reconstructed source tree, checked command files/trace hashes/packets and retained actual CI readback receipts. Limits below are explicit. |

These are50 parameterized tasks, not50 unrelated capabilities. Local explicit
markers and deliberate lifecycle changes do not establish general semantic
understanding or automatic contradiction inference. Supplied diagnostic
truncation metadata is an evaluator aid, not a claimed client-visible field.

## Fixed native and portable evidence

Both required jobs completed/success with all required steps successful:
windows105833357189 and portable105833357065. Each executes the two event formats
claude/codex separately:50tasks and520real task commands each, or2080task commands
across the four CI runs. They do not launch the real Claude or Codex applications.
Windows uses the exact published c26 EXE. Linux freshly compiles the unchanged
runtime and four focused unit targets, with PostgreSQL disabled.

| Downloaded artifact | Identity |
| --- | --- |
| Windows | ID10577225758;1025398bytes;SHA256 1bea56d5ff03d98080ef6102b84a8021d6c60cfa061f17bff4c269d271661d33;3481members |
| Portable | ID10577600178;12913452bytes;SHA256 e9ed3f990cce2059e17ab9c12d054cb851f289b2c2d1fada13846dfccd547c04;3485members |

The1061-file nested source tree and archive comment match the tested tree/commit.
All four engine reports identify11c7 and a clean tracked checkout, fixed corpus,
50passed/0failed,520commands and model/host NOT_RUN. Every recorded stdin/stdout/
stderr file digest was checked, as were trace digests, actual output byte counts,
per-case log labels, packet bytes and original readback report hashes. Empty answer
templates remain genuinely empty. Both platform unit logs contain24tests OK under
normal and optimized Python; portable core log records4/4 groups.

The fixed native EXE bytes were independently recovered from the verified public
ZIP, and the complete provided file checker was rerun against both native task
artifacts. Its SHA256 is c35fadde8c8356b7243bf0b34cfd5c836bda27bb46da87eddcc79c1031bf05b5.
The portable CI EXE was not downloaded. Its reported SHA256
 a36fff1f52975fd8906f58891f91ec225ca523188c020dfd63c23f5f3c471033
matches the CI checker receipts; raw files/packets were independently checked,
without pretending the local GCC14 binary has those same bytes. The final local
binary SHA256 is4aeafbc4b468bce4d0cbb95e58602186f4972a1b372f1a11160a60d67d541c4c.

The local environment is an extracted9feed source tree plus the exact new tool
bytes, not a fabricated git clone; local reports honestly record source_commit:null.
Both final local event-format runs passed50/50 with520commands, and their file
readback passed. Native evidence comes from the actual fixed GitHub checkout.
No new Windows full60-group build is claimed in this tools-only node; prior runtime
acceptance remains its prior evidence, and original tests are untouched.

## Self-review finding and fixes

Grounded accuracy alone could give correct no-context abstention the same100%
as an oracle with-context fixture, misleading an A/B interpretation. The final
contract explicitly names grounded accuracy and adds answerable_resolution over
25known/conflict tasks in both conditions. A separate regression proves fixture
scores of25/25 versus0/25 resolution without claiming any actual model result.
See METRIC-REVIEW.md. Original23 tests remain byte-identical; the new test brings
unit discovery to24. No expectations or denominators were weakened.

Additional review mutates actual output copies: false totals, duplicate cases,
missing commands, wrong/Boolean exits, changed stdout, altered trace count with
updated hash, invented model-PASS, altered context with recomputed packet/key
hashes, contaminated control, wrong key ID and changed instructions. All12reject;
the original input remains untouched and the restored copy passes again.
The tested helper review_task_files.py is committed for reproduction.

Before the final candidate, isolation was strengthened from a changed brain ID
to actual distinct project directories; command count changed515to520. Only the
520-call final runs are accepted. Diagnostic output counts were checked against
actual bytes rather than trusted alone. Unreferenced draft transcription errors
were rejected before commit; final source blobs match the tested files. Earlier
local experiments and the initial23-test candidate are not substituted for the
accepted24-test candidate.

## Scope, retention and remaining gates

Reported durations describe small isolated synthetic data, not throughput at scale.
No paid model was called; provider token/cost fields are null. The offline scorer
validates structured answer content, not its authorship, supplier usage, arbitrary
prose quality, or automatic Hook consumption. Exit0 means a complete valid file was
scored, not all answers correct. Public CI fixtures contain synthetic answer keys;
a blinded real-model evaluation must generate fresh data and isolate keys, command
logs, sessions and both comparison conditions outside the model's accessible files.
The tool is not a security sandbox for an untrusted executable or malicious operator.

Prior Claude/Server2022/N47D live evidence and reported later Claude observations
retain their original scopes; this node does not erase them or relabel them as
current Win11/Codex evidence. The known prior Codex authentication blocker was not
retested. Plugin discovery did not supply a native authenticated client execution
capability. No real user histories/brains, credentials, global configuration or
client trust settings were touched. No fresh host handoff is required for this
repository-capable tooling stage.

SUMMARY.json pins source, artifacts, test results and local derived-record hashes;
CI-READBACK.json records exact per-run identities. The full raw archives remain
Actions artifacts subject to2026-10-03expiry, not secretly embedded in Git. The
small corruption-review receipt and local-source limits are preserved. The closing
docs commit adds only documentation and its already-tested helper; compare its
diff and actual merge tree before merge, and never predeclare merge-triggered CI.

No Release/tag changed. N47O's publicly downloadable installer still lacks N47P's
fix. Real client consumption, actual model A/B, quality/cost, scaling, PG, broader
semantic tasks, ACL/DLP and signing are not passed by this acceptance. The current
v1 planning interval remains3–5 substantive rounds including integrated delivery;
the broader15–25 interval remains conditional and includes v1. Tooling readiness
is not sufficient grounds to decrement external acceptance work automatically.
