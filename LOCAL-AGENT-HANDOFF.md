# Local Agent handoff convention

Owner instruction, September 13, 2026. Applies to all future handoffs for this
repository unless the owner changes it. This is a persistent repository rule,
not a claim to modify ChatGPT global preferences or unrelated projects.

Give exactly ONE complete prompt per handoff, in one copyable block. Do not
split the work into prompts A/B or require the owner to forward a second prompt.
The local Agent may execute dependent steps sequentially inside that one task.

Before handoff, publish every required file in this repository or its versioned
GitHub Releases. Verify availability and integrity. The prompt states exact
repository/tag or commit, download URL, checksum, safe extraction and execution,
limits and expected output. No sandbox attachment or owner-managed file transfer
may be the only route to a required input. A checksum mismatch must stop execution.
Do not reuse or overwrite released bytes silently; publish a new version.

Repository-side development, build automation and fixes remain remote. Delegate
only local environment, installed client, login/trust and actual host tests.
Do not install large toolchains merely to run a verified prebuilt executable.
Preserve local user data, uncommitted changes, existing credentials and permissions.
No false PASS, forced push, destructive cleanup or invented global-setting edits.

Current unified runbook: docs/integration/LOCAL-AGENT-RUNBOOK.zh-CN.md.
Delivery builder: tools/delivery/build_acceptance_kit.py.
Release tag: local-acceptance-n46e-v1 (available only after publication succeeds).
Runtime and helper retain their independently recorded tested source identities.
Release asset publication is file delivery, not a new product/host acceptance.
