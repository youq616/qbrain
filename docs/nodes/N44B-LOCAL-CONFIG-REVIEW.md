# N44B local configuration correction

Reviewer: owner-delegated ChatGPT. Approved for native revalidation, not yet a native PASS.

Run 34613913091 passed 44 registered groups and all native memory/MCP/hook/context process fixtures. The PowerShell installer then caught a real isolation defect: `config set memory.writeback salient --brain PROJECT` mirrored the effective brain_id into global config.json through Brain::save_config_value. `init --no-default` alone could not protect the default selection.

Add an explicit `config set KEY VALUE --brain ID --local` option and a default-true mirror_to_file parameter in Brain. Preserve existing callers and ordinary config command compatibility; the installer opts into DB-only updates. Six real subprocess assertions check unchanged global config bytes, persisted local values across reopening, and absence of changes in the other brain. GCC production rebuild, 82 memory unit checks, 37 context unit checks and 69 hook fixtures passed locally after the amendment. Native rerun remains pending.

The artifact gate also distinguishes whole-line registered group results from nested human-readable N42 assertions. Five unit tests reject missing, duplicate or failing evidence and changed registries. This changes parsing only, not product assertions or the 44-group requirement.

Temporary patch importer removed. Native install gates run before the longer full regression build to detect script problems sooner; the full regression is still required before packaging. No real user configuration, memory or external model key is used.
