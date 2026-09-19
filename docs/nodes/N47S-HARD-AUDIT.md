# N47S final outcome review — controlled model-comparison tooling

2026-09-19, Asia/Seoul. **PASS for the approved execution-tool scope.** No known
unresolved blocking finding remains in this scope; not an absolute defect-free
claim, real-provider benchmark, authenticated-client acceptance or stable-v1 signoff.
Reviewer: coordinating ChatGPT in a separate engineering self-review requested
by the owner. No independent subagent, Claude Code or third-party auditor ran.

## Accepted source and preserved plans

Base main: a1557ca26fea534c62ef332429f4c1fd773b1414.
Original plan/review: 55947748bf2c9676bf3e3ecc42d14add3522a74c.
Session-label addendum approved before correction: ca10f2ab595fc6f4d58e5291aa3f07791b753af2.
Accepted code: **b88698bd041d960edcc2a4a2e9beb6fa407ffc47**.
Accepted tree: **69e581bcd68b6c1e2170b729abc0b0228d577f17**.
Original plan retained at n47s-evidence/APPROVED-PLAN.md; detailed findings remain
in FRAMING-REVIEW.md, SESSION-LABEL-REVIEW-PLAN.md and PROJECTION-IMPLEMENTATION.md.

## Acceptance against the plan

| Criterion | Actual result |
| --- | --- |
| Complete, isolated comparison | Two original 50-task packets remain bound to their evaluator key. A random plan orders adjacent pairs and independent single-task requests; each condition has 50 requests. No tools or earlier request history are sent. |
| Explicit external execution | Prepare/score stay offline. Execute requires exact plan SHA, endpoint and 100-request approval. Key comes only from a named environment variable; test HTTP is numeric loopback-only and refuses credentials. |
| Credential and failure handling | Default verified TLS, no redirects, implicit proxies or retries. Response/header/size/type errors stop remaining calls. A key echoed directly or JSON-escaped is redacted before persistence and rejected; malformed/error text is not saved. |
| Blinded testing metadata | v2 plans bind opaque-session-ids-v1. The model-facing session IDs are pseudonymized, while original packets, quotations and fact/event/item/source fields remain. The projection is disclosed, not claimed as raw Hook-byte replay. |
| Honest scoring and usage | Exact structured replies are validated and mapped back offline. Missing answers stay in both 50-task denominators; 25 answerable tasks are distinguished from grounded abstention. Missing usage/cost stays null; model drift suppresses a comparable delta. |
| Actual execution and later review | Fixed native Windows/Linux CI, downloaded source/command artifacts, independent output comparison, repeated local tests and additional corrupted-copy checks passed as detailed below. |

No production C++, schema, installer, original test/build script, canonical ops
ledger or frozen inventory changed. All 259 inherited runtime/test/script files
match the accepted N47R source. Original N47Q contracts and 24 unit methods remain
byte-identical. Five new Python files and read-only validation workflows implement this
node; Python remains optional evaluation tooling, not a new application service.

## Fixed native run and downloaded artifacts

Push/attempt 1: **35433697805**. Jobs **105872671392** (Ubuntu) and
**105872671530** (Windows) completed/success. Every required step passed; the only
expected skip is Windows-only native engine execution in the Ubuntu job.

| Artifact | Exact pin |
| --- | --- |
| Linux 10581356655 | 12,010,066 bytes; SHA256 97d12e8e333f00ba3bd4af73ce5cdc6edfab0829189a3d3065b53278a3e44c52 |
| Windows 10581891745 | 12,877,650 bytes; SHA256 6bb0fbdb31cd31a73fa83f66f23cec12dc1b1e19036d3d82de3efcfdaf6ca357 |

Both were downloaded in this continuation. ZIP sizes/digests/CRC, source.txt and
source archive comments were checked. The 1,109-file Linux source reconstructs
the accepted Git tree exactly. Windows has the same membership/modes; 1,095 files
have only exact LF-to-CRLF changes, not arbitrary whitespace normalization.
The final core/test/integration blobs match those tested before submission.

Both environments passed **48 methods in normal and optimized Python**. Actual
interpreters: Linux 3.12.3, Windows 3.12.10. The same 48 methods also passed locally
in both modes after extracting the exact accepted source. This is 24 original
methods plus 24 new methods, not 48 new product features.

Windows additionally ran the fixed released EXE against 50 engine tasks and 520
CLI/Hook commands, then a separate child executor made 100 real HTTP requests to
an explicit local test responder and the scorer processed their replies. No real
provider/model or signed-in client was invoked. EXE SHA256:
`c35fadde8c8356b7243bf0b34cfd5c836bda27bb46da87eddcc79c1031bf05b5`.

## Complete native regression gate

After the tool evidence passed, the full unchanged application and original unit
suite were freshly built and run under MSVC. Fixed push/attempt1 **35434346909**,
job **105874373793**, source **db791b0027e807f592917d9221704820f46bf867**, tree
**b8e41cd0800b5ac43da0f4b54ea8ab3a5cba9055** completed/success, with all steps passed.
Compared with b886, this adds only a validation workflow and its gate note.
No implementation or original test/build script changed.

Artifact **10582163047**, 12,073,806 bytes, SHA256
`3c7e19ba161a20eac2b27eff491e69034357fb45005e13ecc1226f577bc52180`, was downloaded.
Its four members, exact source.txt, 1,111-file source tree, BUILD_OK marker and all
**60 registered groups** were independently verified from the original 568,336-byte
native log. The log SHA256 is
`7920b1e06db906d7ed47d51e9d201919b17217b963ba594bfee3716e2b269284`.
The explicit live PostgreSQL SKIP remains; an outer group PASS is not live PG
acceptance. The newly compiled EXE is not equated with the fixed released EXE
used in the separate HTTP pipeline. NATIVE-READBACK.json retains this result.

## Independent output inspection

The exact EXE bytes were recovered from the separately hash-verified public c26
archive, not equated with an unrelated build. The original engine file checker
and final model score_run were rerun offline on downloaded Windows artifacts and
reproduced both recorded results. All 402 HTTP run files were accounted for.

All 100 stored request bodies matched the derived approved plan and contained no
synthetic scenario IDs. A separate structural comparison checked 30 nonempty
contexts and 40 session fields: only the specified session pseudonyms changed;
quotations, fact/event/item IDs, sources, other metadata and original packet bytes
were preserved. Pipeline, plan, engine, run and comparison digests are retained
in n47s-evidence/READBACK.json.

Six additional corruptions of copies of actual CI output were rejected: disabled
projection, relabeling loopback as a provider run, altered request with recomputed
local hashes, changed response, missing row and changed key readiness. Restoring
each copy reproduced the original positive result. No original evidence changed;
ADVERSE-READBACK.json retains the checks. These are consistency checks, not
cryptographic proof against an operator able to replace all files and code.

Additional local TLS socket review confirmed rejection of a temporary untrusted
certificate before any HTTP request. A test-only added trust root then allowed
one synthetic request, with certificate/hostname validation still enabled. No
system trust store changed, no real key was used, and this is not an external
provider integration test. TLS-REVIEW.json retains the result. The original
native-log/manifest validators also passed 42 methods normally and with Python-O.

## Findings closed rather than hidden behind earlier green CI

1. Initial 7024 candidate silently defaulted explicit port zero and could accept
   a short HTTP body containing valid JSON. The separate framing tests reproduced
   four failing subcases against that exact original module. Port and complete,
   unambiguous framing checks corrected these two boundaries; old tests stayed.
2. Later a2fd artifacts passed their 45 methods, but actual request readback found
   scenario names in evidence session_id fields. Empty-context fixtures had missed
   them. After the approved addendum, v2 metadata projection, three nonempty tests
   and the native pipeline's all-request check corrected the gap. The original
   packet is not modified, and literal user text is deliberately not scrubbed.
3. Earlier local baseline invocation initially mixed old/new fixture imports and
   errored. Its corrected invocation produced the intended assertion failure;
   the setup error was not counted as a product regression. The final acceptance
   uses b886 and its fresh artifacts, not either earlier green run.

## Remaining boundaries and decision

This tool targets a specified Chat Completions wire contract; actual vendor/model
compatibility, billing, model-answer quality and authenticated host consumption
still require authorized external execution. CI response text and token numbers
are fixtures. The loopback designation, NOT_RUN host/model fields and null actual
provider cost are preserved. Local hashes do not authenticate a remote provider.

The caller explicitly approves packet content for the chosen endpoint. Fresh
synthetic data and private answer keys are necessary for a blind comparison.
Unknown credentials, secret fragments and arbitrary operator tampering are not
covered by the current key-echo guard. Socket/response limits are not a strict
wall-clock or dollar budget; ambiguous failed attempts may already be billed.
No arbitrary-prose quality, broad semantic inference, scale benchmark, new PG,
real Windows11 client or TLS provider integration is claimed. The separate full
native rebuild above is actual CI execution, not a new product release.

The node is accepted as source tooling. N47R Release 391991518 and all its assets
stay unchanged; this new tool is not silently inserted into the published ZIP.
Closing docs must not alter tested Python/workflow bytes. PR36 records the actual
merge/tree; later merge-triggered CI is not declared passed in advance. Existing
3–4 round v1 / 15–25 round broad estimates remain conditional, because a working
executor does not replace the missing external observations.

Raw CI archives expire under the original retention policy on 2026-10-03. Their
fixed hashes and small derived review receipts are retained in Git; the full raw
archives are not represented as embedded in the repository.
