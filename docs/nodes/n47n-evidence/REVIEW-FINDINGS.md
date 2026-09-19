# N47N separate self-review findings (checkpoint)

Reviewer: coordinating ChatGPT in a separate engineering review authorized by
the current owner request. Not a separate agent or third-party certification.

## Windows standalone-test entry point — blocking validation defect, repaired

The first N47N workflow passed the standalone parser test (which owns main())
to build-tests-cl.ps1 -TestSources. Source inspection during outcome review
found that this option APPENDS to the canonical test closure; it does not
replace test_main.cpp. That would introduce duplicate main definitions. The
original build script is correct and is unchanged. A dedicated small CMake
project now builds/runs only the pure-parser executable, followed separately
by the existing complete native suite. Local CMake build/CTest passed 361
checks. Native results for the repaired candidate must still be verified.

## Punctuation-only fixture expectation — corrected, no product change

The initial process fixture incorrectly required a hit for the literal --.
The unchanged search backend/MCP returns an empty array for that input. The
corrected test asserts equality with MCP and explicitly asserts that empty
result; the pure-parser test independently checks that -- is preserved.
Initial 245/248 and final 248/248 local reports are retained. This repair does
not change tokenization, ranking or product behavior.

## Transfer integrity

Two unattached commands.cpp blob uploads did not match the tested local Git
blob and were rejected before any tree/branch referenced them. Only the exact
8af9f8d829f630cb17247bf65f3aebd54b5324ae blob entered the candidate. The actual
980-file 9484f17a source artifact was reconstructed and all product/build/test
files matched the local tested bytes. The subsequent CI repair changes only
validation setup and this record, not those product bytes.

No product blocker has been found in the scoped parser review so far. This
checkpoint is NOT final acceptance: full native and artifact evidence remain
pending until their actual source-pinned results are inspected.
