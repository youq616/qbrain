# N47A candidate readback: executed result, not an independent review

Checker source: `4588bdd49121460ab28280cf86bdac46884b39ec`.
Product source remains `cccdacb61e63c29f8b9eaba1c38fbeed3e23e54b`,
tree `a15a91f7172622e2c8021403d84e63bf36f59147`.
The two source identities are different and must not be conflated.

## Actual execution

Run [34793874790](https://github.com/youq616/qbrain/actions/runs/34793874790)
completed successfully. Windows checker job 103823110530 and Ubuntu checker job
103823110630 each ran the 16 checker tests. Readback job 103823211740 downloaded
five fixed, externally hash-pinned artifacts from product run 34788803379 and
passed all 81 readback checks. No compiler, application executable or publisher
was invoked by the checker workflow. Permissions remained contents/actions read.

The readback reconstructs the exact 702-file Git source tree, verifies all package
inventory hashes and original native report bytes, then revalidates full fact-unit
contents and process reports. It also checks the 49-name native regression log,
CJK report, both Windows wire/lifecycle schedules and retained process logs.

Fact evidence: 15 unit scenarios, 380 assertions, 34 named process checks and
118 commands. Six command exits are expected negative results, not failures to
be relabelled as all-zero execution. The unit probe hash comes from the original
externally pinned logs; its executable was not independently downloaded here.
The original package job had checked that executable against its report.

## Downloaded result artifact

Artifact ID 10328872158, name qbrain-n47a-candidate-readback, 2608 bytes.
SHA256 `dd9b866f6a3edd4056239baf02f2511d6408322458df99e903ba7b66ac4cb1ad`.
It contains only readback.json and readback.log. Artifact digest, CRC, exact member
list, result/source/tree and 81-check count were verified after download.
The CI JSON bytes exactly equal the locally executed report:
SHA256 `10b70e77cb8a182b5d105b27f6f20f002450a68cf13faafb277e7479ba6cbf5c`.

Original product inner ZIP remains 1909496 bytes, SHA256
`1944813712c96e4096058b75b3b7fc18f6a521cf72851413e4a26135f714eee1`.
EXE remains 3897344 bytes, SHA256
`dead42f5b28d4f296b0b77975e9dbe150f5ac848aac8c6795e2addc7ede53854`.
Neither was changed, repackaged, run or published by this readback.

## Retained failure and correction

Initial checker run 34793615048 passed Ubuntu but failed the Windows invalid-name
fixture. Constructing ZipInfo on Windows normalized a backslash before the
fixture was serialized. The correction writes same-length placeholder names and
replaces both serialized name fields with the intended invalid bytes; embedded
NUL is also covered. The checker now examines orig_filename and refuses any
normalization/truncation rather than trusting filename alone. No original failure
assertion or external artifact pin was removed. The fixed source, not an unchanged
retry-until-green run, is what passed the final workflow.

## Scope and review status

This supplements the current artifact check for the reported P3 publisher
fact-unit observation. It does not edit or re-enable publish_fact_preview.py;
permanent integration into the publisher remains open in issue #16.

The owner reported two independent subagent PASS verdicts for product cccdacb6.
Those reports did not review this newly written checker. This document records
engineering tests/readback only and is not a fabricated independent-agent PASS.
Companion PR #15 remains draft, and product PR #14 is separate. Raw product-review
archive intake is still pending; no repeated local audit, compiler installation,
credential setup or fresh source export is required.

No claim is made of new user-host, paid-provider, PostgreSQL, whole-project or
N47B acceptance. Fixed CI artifacts can expire; the checker must then fail rather
than silently substitute latest or a different product build.
