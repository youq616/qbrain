# N47D — explicit Hook fact recall and one serialized-output budget

Baseline 984707be084591b2251701e29392c9a85e4c7c2f. Approved after N47D-PLAN-AUDIT.md.
Only Windows-native youq616/qbrain. Separate owner-authorized engineering
self-review; no external/subagent identity or bug-free guarantee is implied.

Add installer -EnableFactRecall and config fact_recall (strict boolean, default
false), independent of capture/writeback/provider consent. Existing installations
without the key retain the original Hook path. Status exposes the flag. Reinstall
without the flag disables it; uninstall removes only owned integration config.
Opt-in permits evidence to enter the existing client's model context: this is NOT
an assertion that the client sends nothing externally. Qbrain makes no extra model
call and does not modify authentication, global client configuration or MCP writes.

For enabled SessionStart, retrieve recent active fact neighborhoods; for enabled
UserPromptSubmit, use at most eight unique literal terms from the existing lexical
extractor, total <=1024 bytes. No semantic query generator or CJK word segmentation.
Add a FactStore internal Hook retrieval entry sharing the N47C neighborhood loader,
with a single candidate SELECT and shared 512-check/8MiB evidence budget. Empty
terms mean recent only for SessionStart; a prompt with no usable terms recalls no
facts. Preserve the public single-query recall API and all its semantics/tests.

Compose full fact neighborhoods before ordinary memories, within ONE recall_bytes
limit for the entire serialized hookSpecificOutput JSON (excluding its newline).
max_items applies to neighborhoods plus standalone memory items, not to individual
counterclaims. Never split a neighborhood or truncate quotes. Exclude ordinary
memory items backing any existing fact or having its exact quote, including retired
facts; otherwise a byte-limited or retracted fact could leak back as a single raw
memory. Cross-source quote equality does not suppress a different source. Ordinary
memory dedup remains; fact groups are deliberately refreshed each relevant event,
so changed evidence/revisions are never hidden by session dedup.

An explicit read transaction spans fact selection, validation and ordinary memory
filtering; close it before capture/writeback. Builder failure emits no partial
output. Existing outer Hook remains nonblocking and project/source bound. Store no
prompts, fact quotes or query terms in recall-state or trace. Trace counts/budget
flags are not proof of model consumption. Work limits describe application work,
not SQL row scan count or a hard wall-clock guarantee. Empty+truncated is incomplete.

Tests: default-off and independent capture switches; SessionStart/relevant prompt,
nonmatching counterclaims, old recall compatibility; unified exact byte and item
limits including JSON escaping; no split or ordinary-lane bypass; withdrawn,
expired, tampered and forgotten support; unrelated source/project; repeated prompt
updates; sensitive input; malformed flags; read-only schema/data and no jobs.
Use real second-connection WAL interleaving to verify single-snapshot behavior,
unit-level composition and actual executable Hook process fixtures for both client
adapters. Verify reversible installer under PowerShell5.1 and7, no global state.
Add the 52nd native group and strict source/binary/test/report package gates;
retain all previous native, portable, Server2022, HTTP, CJK, fact and recall suites.
Outcome review must fix blocking findings before integration and exact-byte release.
Real signed-in client consumption is a separate local task, not emulated by fixtures.
No schema migration, automatic fact creation, inference, conflict resolution, decay,
profile or PostgreSQL support is added. Rollback restores old code/config behavior.
