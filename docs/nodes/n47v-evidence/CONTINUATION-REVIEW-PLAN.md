# N47V continuation review plan

Approved under the original N47V plan by the coordinating assistant in a separate
engineering pass. Product source remains192cdec2, installer SHA256(LF)
b2c6b64a4ad33adb9ab7b4d436c2a3427191fec7965482cfa97c2a824f6da64b.
This is not another agent or third-party review.

Run35450108456 attempt1 passed the84 new checks on both native shells, snapshot24
and recovery60. PS7 later timed out at the unchanged Codex encoded Hook in the
original install suite; PS5 and full native passed. Retain that failure and rerun
its identical job without changing the bridge, installer, tests or10s timeout.
Do not infer a root cause merely from a successful retry.

Supplement the original acceptance with22 native review checks: normal native
metadata query, direct regular-file/missing-path rejection, repeated error paths,
and scheduled directory replacement by a file or junction at the Get-Item/native
query boundary for all three actions. Compare all disposable directories/files
before and after restoration of the test-only substitution. A fixed-source new
workflow runs this additional script on both shells without changing or skipping
any original workflow. These controlled substitutions are not a guarantee against
arbitrary concurrent or malicious directory replacement after the last check.

No runtime/installer/schema/default/old-test/Release changes. Outcome remains
pending until both the unchanged failing gate and the new boundary checks are
actually complete, with original artifact and precise attempt/source readback.
