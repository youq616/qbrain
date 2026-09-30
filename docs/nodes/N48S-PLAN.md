# N48S — unified Windows integration candidate through N48R

2026-09-30. Product base e0a27f829d970c24ed8c566023ada0911c0042b3,
tree534c86deabf43e30d3b2533cd3bf1f0728cf8400. Status: approved after the
separate design review. Owner delegates normal development decisions and requests
coordinator self-review. This is not third-party/subagent certification.

## Goal
Deliver one fixed, newly tested Windows x64 candidate containing the existing
runtime, installer, UTF8 bridge, joint evaluation, backup/check, and PostgreSQL
memory/context/facts/Hook documentation. Do not replace historical archives or
claim stable/full-project completion. No new C++/schema/installer behavior.

## Falsifiable acceptance
1. Pin product commit and full Git tree. Reject changed tracked source and payload
   differences. Use canonical source text with only exact LF/CRLF conversion.
2. Inspect actual PE32+ AMD64 ordinary and delay-import tables. Eager imports must
   be explicitly allowed Windows system DLLs; delayed imports exactly libpq.dll.
   Refuse CRT DLL/eager libpq/unknown dependencies and malformed RVA/section/table
   structures. This is direct dependency evidence, not transitive PG certification.
3. Prove the extracted program runs SQLite with PATH limited to Windows System32
   and no libpq/DLL payload. PG still needs a trusted server/client dependency chain.
4. Assemble deterministic ZIP twice from fixed source/binary inputs; verify exact
   membership, bytes and metadata. Construction manifest remains NOT_YET_ACCEPTED;
   acceptance is a later external receipt bound to the unchanged ZIP SHA256.
5. Fresh native Windows registered60 and extracted-binary retained55-step gates.
   Execute new backup/check, model evaluation and actual PostgreSQL Hook workflows
   against the delivered EXE. Original tests keep their assertions and timeouts.
6. Native PowerShell5/7 installation, recovery, old-version upgrade/rollback and
   pre-existing active/revoked receipt preservation. Do not substitute records
   created only after upgrade for a preservation test.
7. Unit tests for dependency parser and archive corruption. Re-read actual
   artifacts and all expected stages, including source/tool/binary identity.
   Missing, interrupted or partially executed stages cannot produce acceptance.
8. Chinese usage, version identities and exact scope. No real owner machine,
   brain, paid provider, secret, automatic capture, release/signing or Issue40 claim.

## Rollback and delivery
New packaging/qualification code, workflow and supporting documentation only.
Runtime and old fixed packages are unchanged. No automatic data or default-brain
migration. Incomplete output remains nonaccepted; do not overwrite an existing
output directory. Any later public release requires explicit matching acceptance.
