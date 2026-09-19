# N47R final outcome audit — integrated preview delivered

2026-09-19 (Asia/Seoul). **PASS for the approved integrated Windows preview delivery.**
No known unresolved blocking finding remains in this limited scope. This is not
an absolute absence-of-defects claim, stable-v1 acceptance or full-project completion.
Reviewer: coordinating ChatGPT in separate engineering review passes requested by
the owner. No independent subagent or third-party auditor participated.

## Precise sources and original plan

The original approved plan remains byte-identical in n47r-evidence/APPROVED-PLAN.md.
Its plan-tree write previously failed twice at platform safety checking. The same
request later succeeded without an alternate write route; plan commit62a36e15
preceded the native candidate submission. Earlier local-only candidate and failures
remain in INITIAL-STATUS.md and the previous attached evidence, not relabeled PASS.

| Object | Identity |
| --- | --- |
| Base main | c4d0d73931e5bb96f8ae4a6041c3c34477734e56 |
| Integrated candidate | 9e9a92b0e0e68ee1b07deafc1085bb01849d08a7 / tree957e322e3bbd9105574cf7ce9487fb07f4b78480 |
| Additional old-to-new upgrade | b7e1b60a40f421c13e494733efbf8ce0420f2aaa / tree4b1a0405ceb9c88f0a219223910c7febc6a59119 |
| Reviewed delivery tools | c67e7799adae86929917ad0faffe99842d77a372 / tree713064092af6a3773f70644b21249f76c376fdba |
| Actual publication | be5d84e223633608929c55bb9dd487ec80f8a699 / tree324785cf77a7954723395d7e33e10f45551ffb3e |
| Public release | 391991518 / windows-integrated-preview-9e9a92b0; published2026-09-19T08:03:11Z |

The85-member ZIP contains the unchanged c26 EXE/bridge, exact Windows-tested N47P
installer and six N47Q evaluation tools, with new guides and per-file manifest.
The ZIP is repackaged, not a newly compiled EXE; component commits remain explicit.
The original manifest/README are preserved as history. Construction-time NOT_RUN
fields stay unchanged, with later acceptance in digest-bound external receipts.

## Acceptance against the approved plan

| Criterion | Actual verification | Outcome |
| --- | --- | --- |
| Exact component integration | Pinned old ZIP/manifest; old EXE/bridge and retained files match; installer is exact9feed CRLF; six11c7 tools match; all84 payload entries checked. | PASS |
| Determinism and corruption refusal | Each of Windows/Linux builds twice, all four ZIPs identical to the reviewed hash.22builder methods pass normally/-O, including substitutions with recomputed manifests and unsafe paths. | PASS |
| Native extracted-bundle acceptance | PS5.1/7 each pass24snapshot,60recovery and unchanged69/16/8/33/33 installation suites; bundled task tools each pass50tasks/520commands for both event formats. | PASS |
| Actual old-preview upgrade and guide | Both shells pass37checks using the exact guide extraction block and original public installer before upgrading paths; original fact ID/quotation, user settings and explicit consent retained, duplicate hooks refused by assertions. | PASS |
| Fresh native regression | New MSVC production/test build completes; original60registered groups verified from raw log; PG remains SKIP-PG. | PASS |
| Review before live publication | Fixed native+upgrade archives read back;27release/verifier methods pass normally/-O; read-only CI actually passes; artifact downloaded and independently rechecked before explicit publish enablement. | PASS |
| Non-destructive delivery and actual availability | New tag points9e9; returned draft ID used; five upload IDs/sizes/digests pinned, pre/post downloads match, five anonymous downloads match. Old product asset remains573791294 with originalec681hash. | PASS |
| Honest current entry and scope | New download/status/upgrade instructions and conditional roadmap; old status/README/plan preserved; canonical ledger and product code unchanged. | PASS |

## Native and publication evidence

Native run35428968503 (push/attempt1): jobs105859910076(full native),105859910257
(Linux bundle),105859910461(Windows bundle) succeed. Linux's Windows-only step
is explicitly skipped, not counted as native execution. Upgrade run35429293475
jobs105860856957(PS5) and105860856792(PS7) succeed. Separate jobs retain their
actual source commits; they are not collapsed into a fictitious one-source run.

All five original artifacts were downloaded and digest/size/CRC checked. The
canonical1078-file source tree matches9e9. The native Git archive has1064 exact
LF-to-CRLF transforms and14 byte-identical files, with unchanged names/modes;
14 historical transformed logs are not UTF-8. The verifier's initial too-strong
archive/UTF8 assumptions were corrected without changing native tests or pins:
only exact byte equality or complete LF-to-CRLF transformation is accepted.
Negative cases reject mixed endings, changed bytes/BOMs/names and modes.

Read-only run35430160564 / job105863178161 ultimately succeeds after queueing.
Artifact10580621876:75391252bytes, SHA256
cfe6ec7e1457b4ef156773d0a666a852895fcf0bd73004ff6cc0fb6e3a937a5a.
Its15members,1086-file source tree,27-test logs in both modes and all five assets
were checked locally. The complete native+upgrade verifier was rerun against its
original archives; results exactly matched the retained CI receipts. The27method
suite was also rerun normally/-O in this continuation. Queueing was never a PASS.

Actual publish run35430794301 / job105864873605 succeeds at every required step,
including repeated live authentication, original-evidence verification, publication
and anonymous readback. Artifact10580288457:75397307bytes, SHA256
2399d38bfed74cd3d8ed9a106614392a90165c1d9f5206a616a46e07b285e19a.
Its19members and1087-file publication tree were downloaded/reconstructed. All five
actual assets match verification/receipt/anonymous hashes and the live Release IDs.
The package equals both read-only and native candidate bytes; native/upgrade
receipts are unchanged. Four checksum rows cover the other four release assets.

The61254828-byte public VALIDATION-EVIDENCE.zip retains all five exact original
artifact ZIPs plus four metadata/readback files. Each original ZIP matches the
previously reviewed bytes. It is optional for ordinary installation, but preserves
reproducibility beyond Actions expiration. Source and receipt hashes/IDs are in
n47r-evidence/SUMMARY.json and RELEASE-PROVENANCE.json. Small receipt files are
copied byte-for-byte from actual publication output, not fabricated summaries.

## Findings, residual limits and closing review

The self-review added the missing real old-to-new upgrade scenario rather than
assuming same-installer reinstallation tests were sufficient. Guide text now
separates construction status from later receipt-based acceptance. The output
checker accepts only the actual recorded native archive line-ending transform;
arbitrary normalization remains rejected. No known P0/P1 remains in this scope.

The release is unsigned and non-latest. GitHub reports immutable:false; no claim
of platform-enforced release locking is made. This publisher never overwrites an
existing release/tag, but a repository administrator can still change future
state. Hash/readback observations are not signing or atomic adversarial protection.
The guide filters the expected asset name and uses a pinned archive; it is not a
general guarantee for arbitrary ZIPs accompanied by attacker-chosen checksums.

Native tests are real Windows CI filesystem/process tests with synthetic data,
not new observation of the owner's Windows11 device or an authenticated client.
The two task event formats do not launch logged-in Claude/Codex. No new model A/B,
provider billing, PG DSN, ACL/DLP, semantic merge/decay or signing acceptance exists.
Model/host fields stay NOT_RUN and cost staysnull. Existing evidence retains its
original scope; stable v1 is not declared by publishing an engineering preview.

Closing changes are documentation/receipts plus restoration of the exact earlier
read-only workflow blobcc2f5b61933a3e88f4c721e4777b058aa77f1d78. They do not alter
builder/installer/runtime/tests, guide bytes, publication helpers, source permission,
canonical ledger or release assets. Compare the final diff and actual merge tree;
newly triggered CI is not predeclared successful. PR35 records the actual merge.

The integrated delivery workstream is closed. The remaining scoped v1 estimate
is3–4substantive rounds, based on the former0–1delivery item now being complete;
real client/answer gates remain. Broad15–25includesv1 and remains a conditional
rough interval, not a guarantee or a mechanical count of messages.
