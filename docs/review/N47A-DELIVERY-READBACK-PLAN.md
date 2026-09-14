# N47A delivery readback — verification-only scope

Candidate runtime remains cccdacb61e63c29f8b9eaba1c38fbeed3e23e54b,
tree a15a91f7172622e2c8021403d84e63bf36f59147. The owner relayed two real
subagent PASS verdicts and 13 P3 observations on September 14, 2026. This is a
relay, not receipt of review-A.md/review-B.md: the 18,340-byte original review
ZIP with SHA256 56cb3a2af17303419bbf38c00d3d9d440cbf7a2caee10bf5fdd521dc4d182adc
has not yet been attached to this session. Do not fabricate those files, findings
line numbers, invocation logs, or a review of newly written tooling.

Both required workflows on the candidate have completed successfully. Develop
an offline read-only verifier for the externally hash-pinned source, native logs,
portable logs, Server 2022 logs and package artifacts from run 34788803379.
It must reconstruct the source Git tree, compare package members and original
reports, revalidate complete fact-unit and process evidence, retained regression
and HTTP lifecycle reports, and identify exactly what was NOT re-executed here.
This directly addresses the current-artifact risk behind the reported publisher
fact-unit revalidation observation without modifying reviewed product code.

Before interpreting any archive, check its exact externally recorded SHA256.
Use memory-only member reads and bounded archives. No installer/EXE execution,
network calls or source-tree mutation in the verifier; output a new JSON file.
Test wrong hashes, malformed/partial unit reports, wrong source/test binding,
changed scenarios/assertion sums, bad process exits and inventory tampering.
Then run on actual downloaded native artifacts. Publish verifier and tests only
on this verification branch; do not enable automatic fact publishing, merge the
product or treat this engineering checker as an independent reviewer.

The 13 reported nonblocking observations are follow-up work, not justification
to rewrite cccdacb6 after its review. N47B and production behavior changes are out
of scope. Independent-review raw intake and stage outcome remain separate gates.
Rollback removes these verification tools/documents only. No database or user
client operation is required for this readback.

Engineering plan check: scope accepted before implementation; bounded inputs,
source/EXE/test provenance, exact report contents and negative tests are required.
No claim of signed artifacts, universal runtime correctness or paid-model checks.
