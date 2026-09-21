# Native Windows positive-fragment fixture correction

2026-09-21. Same coordinating assistant, separate outcome review. Original fixed
run35590240768/attempt1: Linux completed all gates; Windows completed its fresh
production/full60 suite and73 standalone checks, then failed the positive partial-
response test. Artifact10635085930 was downloaded and retained (16668024 bytes,
SHA256 e73a2925b9c9436f107ff838ca391389e2d26fe883a897919ec15e5a7e4e5cc7).

The original peer deliberately slept after EVERY byte. In the native record only
161 stdout bytes had arrived after the2000ms protocol budget: initialization had
finished, the catalog had not. The checker correctly rejected with protocol_timeout;
cleanup succeeded. This is not a production timeout bypass or an Issue40 reproduction.
Sub-millisecond sleep requests are not a portable per-byte scheduling guarantee.

Approved correction changes only the positive synthetic peer: send the same exact
JSON in32-byte fragments with the same between-fragment pause. This still splits
inside JSON and tests incomplete reads, but avoids hundreds of scheduler waits.
No product byte,172 assertion, expected result, checker, timeout or workflow is
changed. The independent incomplete-EOF, oversized frame and stalled-input peers
are unchanged. All172 local cases pass with the corrected peer. Re-run native gates
on the new candidate; the initial failure is not retroactively called a pass, and
the Windows retained suites skipped after that failure remain unexecuted until the
new run completes. The previous three production blobs are unchanged.
