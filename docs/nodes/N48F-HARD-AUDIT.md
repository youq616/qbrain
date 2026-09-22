# N48F outcome review — exact offline whole-pipeline token costing

2026-09-22, Asia/Seoul. **PASS for the approved normalized token-cost module. No
known unresolved blocking finding remains within this scope.** Not a guarantee
of no defects, a supplier-invoice verification, actual savings or stable-v1 result.
Reviewer: coordinating ChatGPT, separate engineering self-review explicitly
requested by the owner; not another subagent or third-party certification.

## Exact scope and sequence

Base main6c4f779ee752bd4043847eb79a6d1a5e694d024e; plan/review commit
95d11564e865edaf051191a06bb079c4d72b7b80 preceded implementation.
Accepted product/test source5990fbc4146f06ca53b1af32cf1996e2ae53914a,
tree43e7bff202da7149761e0123ac9f07e1b8e16687. Fixed push/attempt1 run35695173057.

This continuation found N48E already merged and PR47 already implementing N48F.
It reviewed the actual source, not the previous conversation's stale delivery
state; it downloaded completed native evidence and added independent reference
checks. No new production defect was established during this review, so the exact
candidate product, original tests and workflow were retained. The closure adds
only docs, examples, historical copies and executed review materials.

## Approved acceptance against implementation and evidence

| Gate | Actual result |
| --- | --- |
| Complete bounded offline command | Native cost report is dispatched before ordinary brain initialization. One stdin JSON input,256KiB,512 unique call records,64 rate cards. Exact fields, safe IDs, integer/null tokens and decimal-string/null rates; no provider/raw-message input. Actual malformed inputs reject with fixed errors. |
| Exact money | Prices per million tokens have at most6 fractional digits. Multiplication and aggregate addition use checked uint64; currency strings have12 decimals. Each call, stage, rate and overall amount reconcile to independent Decimal and Fraction references. |
| Explicit unknowns | Unknown usage, unknown rate and absent cards produce null complete totals plus known subtotals. Known zero tokens need no price; unknown usage at a zero rate remains unknown. Empty submitted sets total zero but billing/all-calls-observed flags stay false. |
| Failed and retried calls retained | Outcome never suppresses reported usage. Attempt values1–100 and explicit unique call IDs keep failure/retry counts visible. No automatic de-duplication of different IDs or presumption that retries are free. |
| Canonical and grouped output | Sorted input IDs and normalized decimal rates give stable output/digest; record/card permutations and equivalent rate spellings match. Group provider/model and per-component price metadata match a full independent expected report. |
| No side effects | Early dispatch reads stdin, not secrets, settings, user brain or providers. Isolated-HOME sentinel tests show no files/directories changed. Source inspection finds no process/network/database operation in this module. |
| Native and inherited tests | Windows/Linux cost103 direct checks and149 process assertions per Python mode; original Windows production/full60, six Linux core/batch groups, OpenCode lifecycle and N48D172 plus14 retained process suites all complete. |

The only changed inherited production file is main.cpp, with7 added lines. The
162-line accounting header and standalone cost test project are new. Root CMake,
old tests/build scripts, registry, MCP, database, OpenCode, Hook, bridge, permissions
and canonical operation inventory remain unchanged. This prices supplied records
across six named stages; it does not automatically capture the complete pipeline.

## Actual native evidence and byte readback

Run35695173057, push/attempt1: Windows106640349584 and portable106640349810 and
every required step completed/success. Both freshly compiled their product and
the new independent cost target. Original archives were downloaded and verified:

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| portable10680480725 |19540095|2bb49450c69f9a65ff1158811b5ccb2dd97c0dd796e067afc06897e9b65fe557|
| windows10680388945 |18539190|aef6e762903e426a7acebf89f5913eeb37daf31656cb2b9e263176ddb41ac698|

The1308-file canonical source tree exactly reconstructs43e7bff. Windows has the
same membership/modes;1294 files differ only by exact LF-to-CRLF transformation.
Product SHA256: Linux25d99a4aa12a225c375d5655c6f23003f3305c5447d0a696977c8c51b93bdbc7;
Windows0e9e139ecb4b31783ad99c8ae7e7f236a5682393c108226a7a0cf6b793dde819.
Each of four cost reports binds149 checks,148 actual CLI calls and444 raw files,
including92 successful Decimal-reference outputs and56 refused inputs. The
source-owned checker and12 mutations were rerun against exact EXE/test bytes.
An additional full Fraction comparison verifies every one of those92 successful
records per report, including metadata not independently named in the old oracle.

Sixteen OpenCode driver steps and18 retained-driver steps per platform were
checked against exit codes and raw-stream/log digests. Original lifecycle6 reports
per platform were revalidated, along with direct1162/486/1345/164 (Windows) and
1164/529/1345/164 (Linux). Batch89, integrity123, persistent-MCP72, usage75, pages71,
facts34, multiterm112, Hook52, lifecycle40, arguments60/search226, memory44 and
MCP17 retained their own original assertions and recorded validators. Context65
has summary evidence rather than saved per-command bodies; none were invented.
N48D's172/96 output was revalidated. Windows BUILD_OK and all60 registered groups
were read from the original log. Live PostgreSQL remains SKIP-PG.

Normal and optimized offline readback produce identical result files. Initial local
inspection assumed a different archive filename and header directory, then used the
Windows-only validation flag for a Linux record. These local inspection/adapter
errors were corrected against actual filenames and per-platform validator contracts;
they were not product failures and no original assertion was weakened.

## Separate rational-reference and sanitizer execution

The reviewed supplementary plan precedes review_cost_reference.py. Its Python
Fraction reference imports neither product code nor the original Decimal oracle.
It compares complete expected JSON including exact field types, per-component
price, provider/model labels, outcomes, totals, tokens and canonical digest.

The downloaded Linux product passes398 actual calls/1237 assertions separately in
normal and optimized Python:256 independent missing-usage/missing-rate masks,
81 missing-card combinations,24 mixed multi-stage/card scenarios and their shuffled
forms,512 calls/64 cards, alternate decimal spellings and nested escaped duplicates.
The exact scaled uint64 ceiling18446744.073709551615 is accepted. Adding one
0.000000000001 unit refuses cost_overflow, and that exact known subtotal remains
visible if another component is unknown. Eleven modified real-result cases reject;
the unmodified control passes again. These are repeated boundary combinations,
not1237 separate product features or evidence of genuine supplier charges.

Original Linux149/148 tests were rerun in both modes; the downloaded direct binary
passed103 checks. A fresh Clang ASan/UBSan build of the unchanged direct target
also passed103 checks with leak detection and an empty sanitizer error log. This
is a direct-test build, not a new full product build, Windows execution or actual
provider call. Precise records and result hashes are in SUMMARY.json.

## Usage constraints and deliverability

The caller must supply mutually exclusive buckets. Different vendors' cached-input
fields cannot be blindly added: official Claude prompt-caching documentation
separately defines uncached input, cache reads and cache creation. Checked source:
https://platform.claude.com/docs/en/build-with-claude/prompt-caching . The original
Decimal reference's numerical properties were cross-checked against the official
Python decimal documentation; the separate oracle uses rational arithmetic instead.
No live rate value or model recommendation is imported into code or examples.

Each record has one rate card and one price per bucket. Mixed tariffs/TTLs within
one bucket are not inferred; mark an unrepresentable price unknown rather than
inventing an average or fake invocation counts. Currency is a three-uppercase-letter
label, not validation against an authoritative currency registry. Counts/provider
labels are supplied claims. Complete means all submitted token components are
priceable, not that all calls were captured or the bill verified. Taxes, fees,
discounts, FX conversion and supplier-specific rounding/minor units are outside scope.
The uint64 ceiling applies to all known subtotals even when other costs are unknown.

The tested synthetic example totals0.003660000000 and includes a failed first
attempt, a successful retry and extraction. It is not a real vendor quote. The
PowerShell recipe uses the existing UTF-8 process bridge; recipe text itself is
not another newly executed Windows session. IDs and report content supplied by
users are not automatically anonymized, though prompts/responses are not accepted.

Final closure must preserve tested product/CI bytes, compare its documentation-only
diff and reread the actual merge tree. Do not predeclare new merge CI successful.
No new Release/tag, real cost savings, model-consumption, Issue40, PG or signing
gate is closed. Actions originals follow2026-10-06 retention; derived records and
supplementary test code do not replace permanent raw native archives.
