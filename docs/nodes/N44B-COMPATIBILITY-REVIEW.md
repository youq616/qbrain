# N44B native compatibility amendments

Reviewer: owner-delegated ChatGPT. This is not an independent or Claude Code review.
Status: approved for native revalidation, outcome pending.

Run 34612258237 compiled the production executable and passed all 44 registered regression groups and real process fixtures. Installation then failed in PowerShell 5.1: File.Replace received an empty backup path. Use System.Management.Automation.Language.NullString.Value for a true null .NET string, preserving atomic replacement rather than replacing it with a delete/copy workaround. Reference: https://learn.microsoft.com/en-us/dotnet/api/system.management.automation.language.nullstring

Tighten per-installation capture to the actual EnableCapture switch, including a previously opted-in shared brain. Reinstall without the switch is recall-only; do not silently alter the shared brain's persistent policy. Add both-shell regressions.

Compare project and cwd directory filesystem identities instead of case-folded or case-sensitive path strings. Walk at most 256 ancestors to prove membership. This accepts ordinary Windows case aliases without granting a different directory in a case-sensitive subtree. The existing 69 local host-fixture assertions passed after this change; native case-alias checks remain pending.

Preserve all original tests. Add real installer consent/path tests before packaging, retain third-party license text and Chinese usage instructions. No merge or verified package claim until native checks complete.
