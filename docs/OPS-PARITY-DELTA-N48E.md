# N48E delta — complete project configuration lifecycle integration

Integrates local A/B/C functionality as native opencode lifecycle commands before
normal brain setup. No new MCP tool, schema, collection default or implicit write
permission. N48D and all existing core behavior remain. The canonical ledger is
unchanged because this node adds a local integration workflow, not new MCP operations.

Windows/Linux lifecycle tests and pinned OpenCode1.18.31 loading/connection pass.
Native V2 and actual model consumption/cost remain NOT_RUN; V2 stage timeout is not
preserved by the tested V1 compatibility loader. No release/tag is replaced.
[Audit](nodes/N48E-HARD-AUDIT.md) binds source, native/host builds and review records;
[usage](integration/OPENCODE-LIFECYCLE.zh-CN.md) documents explicit reconciliation
and private before-images. Issue40, PG, signing and stable-v1 remain independent.
