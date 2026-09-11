# Qbrain development status - 2026-09-11

Repository: `youq616/qbrain`. Original `Lordakee/qbrain` remains unchanged.
Main baseline: `c65f8686b5f7a9c730df9f1770af400ae801d6ea`, imported from MIT revision `2e5c4f0bf310ca4f340b3a2295d2dfd79d3b8325`.
Development: `optimization/n42-foundation`, PR #1. Full roadmap: issue #2.

## N42 bounded foundation repair: validated

Tested code: `d8fcec42b343668836af6974e38c05550083a655`; later completion updates are documentation only.
Workflow: https://github.com/youq616/qbrain/actions/runs/34556246262

Windows/MSVC full application build passed. Original 41 test groups plus the new N42 group: 42/42 PASS. Real executable stdio MCP integration: 17/17 PASS with successful cleanup. Three focused CTest targets passed under each of GCC and Clang. Raw log artifact hashes and exact scope are in `docs/nodes/N42-HARD-AUDIT.md` and `docs/nodes/n42-evidence/RESULT.json`.

Actual PostgreSQL integration was not run because `QBRAIN_PG_TEST_DSN` was absent. Real model providers and actual Windows 11 Agent lifecycle integration remain unverified; the Windows CI result is not a claim about those environments.

## Delivered code

Cross-source search identity; correct-source synthesis evidence; UTF-8 bounded excerpts; affected page/fact authorization; no implicit image upload; no save in read-only MCP synthesis; rerank validation; and Windows CRLF macro continuation. No new runtime service or schema/data migration.

Native testing exposed and fixed a parser newline bug and a Python test SQLite cleanup bug. Original golden outputs and assertions were retained. Normal CI has read-only repository access; one-time source application workflows were removed. The initial `.ci/n42.applied.json` records first application, not current post-repair file hashes.

## Remaining work

Semantic session extraction, automatic Agent recall/capture hooks, semantic directory L0/L1 layers, full gbrain protocol, all-operation ACL review, Windows Unicode argv and total-cost benchmarks are issue #2 work. N42 completion does not complete these features or imply universal token savings.

## Historical binaries are not the repair build

`dist/` contains upstream artifacts, not rebuilt N42 binaries. No new installation package has been released. Do not overwrite a working executable or migrate production memory using those old files. The new tests use disposable synthetic data; user memory and credentials were not published.
