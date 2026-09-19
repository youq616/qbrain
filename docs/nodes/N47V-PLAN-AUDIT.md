# N47V plan review

2026-09-19. Reviewer: coordinating ChatGPT, separate owner-authorized engineering
plan self-review, not a subagent/third-party review. Verdict: APPROVED.

The user allows normal repository development without repeated confirmations.
The explicit Issue2 identity gap is reproducible without accounts/model calls.
Rejecting unsupported paths is safer than changing a longstanding lowercased ID
while Hook/runtime components still assume case-insensitivity. Do not call this
full case-sensitive support or promise automatic migration/cleanup.

P0/P1 plan blockers: none. Require actual two-directory tests with independent
file identity and distinct sentinel bytes, baseline status collision and candidate
nonmutation. Query all relevant ancestor directories, including managed data and
recovery destinations, and error if the query is unavailable. Keep the old install
ID and opt-in flags on normal paths; preserve all original tests and artifacts.
No directory sensitivity cache, destructive probe, elevation or hidden fallback.

Metadata handles must be closed even on a rejected path; validation is not a
filesystem transaction or hostile-administrator defense. Product uses only
read-attribute rights. Tests may elevate solely to construct disposable NTFS
fixtures; inability to construct them must not become a successful skipped test.
Current signed-in client/model/PG acceptance and the public release stay unchanged.

Primary interface references checked: Microsoft Learn FILE_INFO_BY_HANDLE_CLASS,
GetFileInformationByHandleEx, and Windows per-directory case-sensitivity guidance.
https://learn.microsoft.com/windows/win32/api/minwinbase/ne-minwinbase-file_info_by_handle_class
https://learn.microsoft.com/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex
https://learn.microsoft.com/windows/wsl/case-sensitivity
