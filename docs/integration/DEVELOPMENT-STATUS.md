# Qbrain development status - 2026-09-11

## Repository

Development destination: `youq616/qbrain` (owner selected and authorized).
Original `Lordakee/qbrain` is unchanged. Its exact MIT source baseline `2e5c4f0bf310ca4f340b3a2295d2dfd79d3b8325` was imported as commit `c65f8686b5f7a9c730df9f1770af400ae801d6ea`.

N42 foundation implementation is in Draft PR #1. The complete optimization roadmap is issue #2. A successful import or build is not a complete memory-system acceptance.

## Code delivered

Cross-source search identity, source-correct synthesis evidence, valid UTF-8 display excerpts, affected page/fact read isolation, no implicit image upload, read-only MCP synthesis cannot save, rerank identity/index validation. The exact verified application manifest is `.ci/n42.applied.json`; preimage/replacement evidence is `.ci/n42/edits.json`. The one-time encoded transport and importer were removed after application. The working tree contains ordinary readable source.

## Validation and boundaries

Fresh local GCC and Clang focused CTest targets passed. Full production application compiled under GCC; the real executable passed seventeen stdio MCP checks against a migrated disposable SQLite brain. The same test is now registered in native Windows CI. CI reports the exact tested commit and preserves logs even on failure.

The initial Windows/MSVC application build has passed. Full native regression was still executing when this status file was prepared; consult Actions rather than treating this sentence as a PASS. No real PostgreSQL/model provider/Windows 11 Agent lifecycle acceptance is claimed. Source checks are not a complete audit of every operation.

CI is now read-only with respect to the repository: it builds, tests and uploads evidence, but does not modify or push source. Python is only used for test tooling, not required by the C++ product.

## Important

Files under `dist/` are historical upstream artifacts, NOT builds of the N42 fixes. Do not install those files as an optimized release. Do not overwrite an existing application or migrate a production memory database based only on this development branch.

Semantic session extraction, automatic recall/capture adapters, semantic L0/L1 directory summaries and total-cost benchmarks remain separately tracked work. No claim of complete gbrain parity or universal token savings is made.
