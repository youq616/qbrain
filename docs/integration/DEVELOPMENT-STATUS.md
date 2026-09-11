# Qbrain development status - 2026-09-11

Repository: `youq616/qbrain`. Original `Lordakee/qbrain` remains unchanged.
Main baseline: `c65f8686b5f7a9c730df9f1770af400ae801d6ea`, imported from the original MIT revision `2e5c4f0bf310ca4f340b3a2295d2dfd79d3b8325`.
Development: `optimization/n42-foundation`, PR #1. Roadmap: issue #2.

## Delivered code

Cross-source search identity, source-correct synthesis evidence, bounded UTF-8 excerpts, affected page/fact source checks, no implicit image upload, no save in read-only MCP synthesis, rerank identity/index checks, and Windows CRLF macro continuation. Source includes focused tests and real-process MCP integration plus native MSVC CI. No new runtime service or database migration.

## Validation checkpoint

Code tested by the current workflow: `d8fcec42b343668836af6974e38c05550083a655`.
https://github.com/youq616/qbrain/actions/runs/34556246262

GCC and Clang focused tests: 3/3 each. Full production GCC build and real-process MCP: passed. Current Windows complete application build and real MCP test: succeeded. Full original regression was still executing at this documentation checkpoint. The outcome review is therefore PENDING, not PASS; see `docs/nodes/N42-HARD-AUDIT.md` and the actual Actions result.

Earlier native CI exposed a CRLF parser bug and a Python SQLite-handle cleanup bug; both have actual fixes and added/reused tests, not suppressed failures. The raw artifacts are the audit evidence when a parsed log summary disagrees.

## Not delivered yet

Semantic session extraction, automatic Agent recall/capture hooks, semantic directory L0/L1 layers, full gbrain protocol, full-operation ACL audit, exact token/cost savings, real PostgreSQL/provider acceptance, and host-level Windows 11 Agent testing. Each is separately tracked in #2.

## Do not install historical binaries

`dist/` contains upstream historical artifacts, not rebuilt N42 binaries. Do not replace a working executable or migrate a production memory database based on this branch. New tests use disposable synthetic data. No user credentials, databases or full sessions were published.

The one-time import/patch transport workflows were removed from the development branch after verified application. The remaining CI has read-only repository permissions. `.ci/n42.applied.json` records initial application, not current post-repair file hashes.
