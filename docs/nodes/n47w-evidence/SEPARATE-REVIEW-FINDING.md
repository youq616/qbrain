# N47W separate outcome-review correction

2026-09-20. Reviewer: coordinating ChatGPT, separate engineering self-review.
The first candidate's two native diagnostic steps passed. Before accepting the
stage, source review found its test-only cleanup treated a PID file as sufficient
process identity. A recycled PID could target a different process during cleanup.
This is a test harness finding, not a demonstrated cause of Issue40.

Require the process executable path to match the exact fixture executable before
calling Kill; inaccessible or different identity means no termination. Keep the
process object alive through that decision and disposal. Exercise the refusal on
the current PowerShell process in the existing descendant-cleanup check. All29
original check names and original assertions remain, with this extra conjunct.
No production process-tree kill or product code change is introduced.

The bridge, C# child, checker, old tests and workflow are unchanged. Re-execute the
same native checks with the repaired harness before final acceptance. A successful
old harness run is not evidence of the new cleanup guard. The fixed local test
file's blob was compared with the submitted blob before commit.
