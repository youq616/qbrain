# N47D evidence intake and exact-state helper: outcome review

Verdict: PASS for this scoped intake and acceptance helper. Reviewer: ChatGPT,
separate owner-authorized engineering self-review, not an independent subagent
or third-party audit. This is not a new product implementation or an assertion
that all runtime behavior is defect-free.

## Three different identities

The uploaded live evidence concerns N47D product
`5275045c4790b802b620ba0af52ec6248cd587d5`, Claude Code 2.1.270 and Windows
Server 2022. Current main already contained N47E product
`c6c76a2f3fd2dd0b07326ef6e19c1a59283402e8` when this continuation started.
The newly implemented helper is source
`daaa2024f3f5c933cf1b39a63e1d95bf3a7caceb`, tree
`2b13f79421e6fa11061a86c1564aaed5eb23002f`.
Neither the live result nor the helper's tests are silently transferred to the
N47E automatic-promotion live-client claim. The N47E product remains unchanged.

## Supplied evidence accepted within its recorded scope

The uploaded ZIP is 18,070 bytes, SHA256
`ce25c2459a47ee49c55f1ad5f6e2938e77f9bb14f1f06711851c09af022e93d9`.
All 16 members pass CRC verification; 26 cross-checks compare source identity,
unique check IDs/counts, three distinct session results, transcript-derived Hook
summaries, manually prepared seed evidence, forget and reinstall/uninstall records.
The machine summary has exactly 24 checks: 23 PASS and one prior Codex BLOCKED.

A1's supplied result includes both synthetic prefixes and unresolved conflict;
A2 includes only the surviving prefix; B1 includes neither. Post-forget CLI JSON
contains the complete no_live_recorded_conflict enum, an empty contradictions
array and the surviving quote. The source attachment is not rewritten.

The archive does not contain the full original client transcripts or complete
Hook output JSON. It contains result JSON and transcript-derived summaries.
The local agent's observation of Hook attachments is recorded as such; this
coordinator did not independently authenticate those transcripts, repeat a real
client session, inspect the user's real directories, or infer absence of all
possible tool use from a one-turn result. The supplied evidence is sufficient
for the reported scoped N47D acceptance, not an unrestricted client certificate.

Only a derived receipt and original member hashes are committed at
`docs/review/n47d-live-20260915/RECEIPT.json`. Raw client usage/cost metadata,
local user paths and full original archive remain in the conversation attachment,
not the public repository. Codex's old 401 was not retested or modified.

## Actual diagnostic issue and implementation

The supplied A2 contains_recorded_conflict flag is true even though the exact
state is no_live_recorded_conflict, which contains that substring. Text presence
cannot determine the enum. This was an evidence-summary ambiguity, not a confirmed
product defect. The original evidence is preserved and the limitation recorded.

`tools/acceptance/inspect_hook_context.py` interprets only already-available
structured Hook output or decoded additionalContext. It reads each complete
fact_groups[i].conflict_state value and basic array coherence, not model prose,
user quotes or keyword presence. It does not validate fact authenticity, execute
Qbrain, read client history, wrap Hooks or claim model consumption.

The outcome review checked bounded input, UTF-8/NUL/duplicate-key/nonfinite/depth
rejection, strict event/state/flag types, group/item caps and complete-state counts.
The only output file is exclusively created: existing evidence/input is never
overwritten. Error output uses stable codes, not private parser excerpts. Success
contains counts and the input digest, never quotes/source identifiers. Empty or
truncated input never proves no memories/conflicts. INSPECTED is not an acceptance
PASS. Unsupported legacy formats remain outside the helper's declared scope.

[Workflow 34924390799](https://github.com/youq616/qbrain/actions/runs/34924390799)
completed successfully. Windows job104239207492 and Ubuntu job104239207565 each
ran all 19 tests; their actual logs were read, not just their status flags.
Workflow permission is contents:read and no compiler, product process or model
is invoked by this helper CI.

Separately, 36 actual synthetic Hook envelopes produced by the recompiled N47E
executable were successfully inspected, with both exact state values observed.
Six old-format responses were explicitly out of scope, not reported as product
failures. The unchanged original fixture retained all 52 checks and 72 commands.
This is executable-format compatibility, not another live client acceptance.

No unresolved P0/P1 issue was found in the scoped helper review. Basic shape
coherence is not a cryptographic proof, complete evidence validation or protection
from a local actor rewriting all source evidence. These limitations remain
explicitly false in the machine output and explicit in the handoff instructions.

## N47E verification completed here, not newly implemented here

Downloaded the fixed source, Windows logs and package from successful product
run34906704753 and checked their externally recorded SHA256 before use. Source
archive760 files reconstruct tree07f00ef07fc1cb79642472b63052221c84bb2db1.
The original inner package1986872 bytes and executable3965952 bytes match the
fixed hashes. Manifest size/digest checks and original packaged report bytes
match the downloaded Windows logs. Full promotion reports and the original
53-group registry were revalidated; real PostgreSQL DSN skips remain explicit.
Diagnostic unit probe binaries were not separately downloaded, and their hashes
come from pinned original reports and the original package job's file checks.

Rebuilt unchanged N47E source locally with GCC on Linux and ran:

| Actual local check | Result |
| --- | --- |
| Production, promotion and Hook-composition targets | Build PASS |
| Promotion standalone unit | 18 scenarios / 237 assertions |
| Real promotion CLI/MCP/synthetic Hook fixture | 68 checks / 77 expected exits |
| Existing Hook fact composition unit | 13 scenarios / 229 assertions |
| Existing real-executable Hook event fixture | 52 checks / 72 commands |
| Promotion/Hook/registry report unit tests | 13 / 12 / 15 tests |

All seven commands returned their expected successful outer exit. Negative child
commands retain their declared expected failures. This is Linux re-execution,
not new Windows product execution. Archive-only local reports correctly retain
source_commit=null; source identity is separately established by archive/tree
verification. Final source diff is empty and the source tree remains unchanged.

Public Release promotion-preview-c6c76a2f was fetched again: it is a published
prerelease, product ZIP size and digest match the original CI bytes. This review
compared public metadata to the downloaded CI package; it does not claim a second
direct download of the public binary. No repack, new EXE or product release here.

## Only necessary local next step

N47D used manually created fact seeds. N47E's new boundary is actual client
UserPromptSubmit automatically capturing, locally extracting and promoting a
new preference before another independent session recalls it. This requires
the owner's authenticated client; repository fixtures do not replace it.

Use the single task `docs/integration/N47E-LOCAL-ACCEPTANCE-v2.zh-CN.md` at fixed
commit daaa2024f3f5c933cf1b39a63e1d95bf3a7caceb. Its SHA256 is
551fcc4f6c1957d0314ff742a134b2b7012592f4fcf3be018d1c79658bc9a4d0.
The helper at that same commit has SHA256
46817e5e2eac23de06d5b8b1d433ef57499d5d5367293d93bed80f7e3ebde355.
Both blobs were checked against the exact local files. The task allows at most
three genuine independent Claude sessions, forbids manual seed substitution and
Hook wrapping, retains normal login/trust, and uses isolated test brains only.
If raw Hook data cannot normally be obtained, state the limitation; do not invent
it for the helper. One redacted ZIP suffices, with no compiler, GitHub write
credential, Codex credential change or repeated N47D audit required.
