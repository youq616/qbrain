# Separate checker review: newline semantics

2026-09-19 Asia/Seoul. Reviewer: coordinating ChatGPT, separate self-review.
The native n31a_ledger_rows function was extracted unchanged into a local C++
probe. The new Python check at 5517e9be used splitlines(), and its CLI read_text()
normalized newlines. Replacing all LF separators with CR, VT, FF, NEL or LS made
the Python check pass while the native parser found zero rows. This was a real
checker false-positive, not a search product defect or a reason to weaken N31.

The checker now reads raw UTF-8 bytes and splits only on LF. LF and CRLF retain
104/4 rows; six other separators (including PS) are rejected. A new unit test
exercises direct validation and actual CLI under normal and optimized Python.
18/18 tests pass in both modes locally. All eight variants agree with the exact
native parsing function. The earlier 17-test run remains historical evidence.
The C++ comparison ran on Linux, not a Windows runtime-registry execution.
Fresh fixed-source CI and final artifact review still required before closure.
