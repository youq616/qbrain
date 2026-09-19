# First N47V native harness failure

Candidate cd39d4ff5c584ae6048bd152409e8f40935b5268, push run35449398855.
Both native shell tasks failed before building the first case-sensitive fixture.
The harness named a function Dir, but PowerShell's built-in Dir alias takes
precedence and invoked Get-ChildItem against a nonexistent relative path.
The exact PS5 job105913814434 log identifies line95 and Get-ChildItem. This is a
fixture startup bug, not an observed product failure or an unsupported NTFS host.
Original executable/installer hash checks and source checker tests had passed.
The original installation suites were skipped after this failure, not passed.

Rename the helper and call sites to New-N47VDirectory. Product installer and all
81 expected assertions/flag observations remain unchanged. Rerun the full native
workflow on the new source before acceptance. Preserve the failed run and artifacts;
do not treat earlier or pending full-native output as the new candidate's result.
