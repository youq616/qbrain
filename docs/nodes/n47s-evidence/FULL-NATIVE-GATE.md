# N47S final native regression gate

2026-09-19. Approved additive validation only. The b88698bd evaluation candidate
has completed its Windows/Linux validation and artifact readback, including all
48 unit methods and the real fixed-runtime -> loopback HTTP integration. Keep
those exact results and source identity; they are not a real model benchmark.

Before final stage approval, retain the repository-wide native regression gate:
freshly compile the application and unchanged complete original MSVC unit suite,
then verify the 60 registered groups from the actual log. This is additional
validation, not a runtime implementation change or a replacement for b886's
fixed released EXE used in the model-execution pipeline. Record the native job's
own commit/run and any explicit PG skip. Do not equate its unretained compiled
EXE with the fixed c26 executable by filename alone.

Only this record and one read-only workflow are added after b886. Original source,
tests, build scripts, evaluation modules, permissions and release assets remain.
Final self-review must inspect this result before marking the node complete.
Reviewer: coordinating ChatGPT in a separate owner-authorized engineering pass;
not a separate subagent or third party.
