# N47R separate native outcome and delivery-tool review

2026-09-19. Reviewer: coordinating ChatGPT, separate engineering self-review under
owner authorization. Not a subagent or third-party certification.
Verdict: native integration/upgrade scope PASS; publication remains pending.

## Actual fixed test objects

Integrated candidate source9e9a92b0e0e68ee1b07deafc1085bb01849d08a7,
tree957e322e3bbd9105574cf7ce9487fb07f4b78480, push/attempt1 run35428968503.
Full-native105859910076, Linux bundle105859910257, Windows bundle105859910461
all completed successfully. The Linux-only Windows step is explicitly skipped,
not a simulated Windows PASS. Four builds across two platforms are byte-identical.

Additional upgrade sourceb7e1b60a40f421c13e494733efbf8ce0420f2aaa,
tree4b1a0405ceb9c88f0a219223910c7febc6a59119, push/attempt1 run35429293475.
PS5 job105860856957 and PS7 job105860856792 passed37 checks each. The exact
SHA-pinned guide extraction block was executed, including checksum/existing-dir
refusal; old public installer -> new path upgrade preserves the original fact ID
and quotation, unrelated configuration, explicit consent and default-off behavior.

The same4858530-byte ZIP was tested in all jobs, SHA256:
e7158949d805a0a25157bfb720561e4b21e80a433a6c7f031c60ee3bbaa746c5.
It is repackaged; its c26 EXE is not recompiled. N47P installer and six N47Q tools
remain exact independently pinned bytes. Internal manifest status is construction-
time only; later evidence binds acceptance to the ZIP without changing it.

## Executed original regression and evidence readback

Each native shell passes24 snapshot cases,60 recovery cases and unchanged
installer69/consent16/transport8/fact-install33/promotion-install33 checks.
Bundled task tools pass50/50 cases and520 native process calls per event format.
Fresh MSVC production/test build passes all60 registered groups; PG stays SKIP-PG.
Builder22 methods and bundled tool24 methods pass normally and with Python-O.

All five original artifacts were downloaded and checked against connector pins:
windows10579886985, linux10579304715, native10580126897,
upgrade5 10579509829, upgrade7 10580057003. Hashes and sizes are fixed in the
publisher. The complete verifier checks source tree, exact ZIPs/receipts, native
report identities and ordered logs, original unit groups, and raw task-file checks.
Native and upgrade readback both completed locally, not merely CI status queries.

## Review findings retained

The first draft offline checker incorrectly required the Windows git archive to
have the canonical Git tree bytes. Inspection showed1064 files are exact whole-
file LF-to-CRLF transformations and14 unchanged files; names/modes match across
1078files. Fourteen transformed historical logs are not UTF-8. The corrected
checker retains the independently hash-verified canonical Linux tree and accepts
only exact byte equality or precise LF-to-CRLF transformation; it does not decode
or normalize arbitrary text, BOMs, mixed endings, content or permissions. Added
negative cases cover these boundaries. No product/native test or pin was weakened.

Guide text now separates build-time NOT_RUN from later external acceptance. The
old local candidate remains historical, not relabeled as the final native-tested
ZIP. Earlier platform safety blocks were retried through the same operation only.

## Publication-tool review before read-only CI

The three new source blobs match their locally tested bytes. New verifier/publisher
11 methods plus retained14 state-machine and2 transport methods pass in ordinary
and optimized Python,27 methods each. Coverage includes fixed run/attempt/source,
mandatory steps, incomplete reports, altered upgrade records, unsafe ZIPs,
wrong tags, drafts, upload failures, asset replacement and anonymous corruption.
Fixture APIs are not real publication. Live read-only authentication must pass next.

The old transport/identity helper is SHA-pinned, not modified. New publication
preserves draft returned-ID use and immutable tag/asset checking, and correctly
states this ZIP is repackaged. No delete/clobber/tag-move fallback exists. New
publication is an explicit flag; current workflow is contents/actions read-only.
Only after its actual run and separate result review may permission and flag be
changed. The release evidence is designed to retain all five original artifact
ZIPs, not just derived totals, beyond Actions retention.

No real user machine, client login, model call, provider billing, PostgreSQL or
signing acceptance is asserted. Hashes are not signatures; checks are observations
rather than atomic protection against a malicious concurrent administrator.
No known blocking finding remains in the native integration scope; public delivery
and whole-project completion are not predeclared.
