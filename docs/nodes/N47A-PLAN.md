# N47A — evidence-backed fact versions

Status: done for this scoped storage/lifecycle stage after N47A-HARD-AUDIT.md.
Independent source reviews A/B on cccdacb61e63c29f8b9eaba1c38fbeed3e23e54b
and separate native runs 34788803379 / 34788803239 passed. Original review files
were received and preserved on September 14, 2026; 13 nonblocking P3 observations
remain tracked in issue #16. This is not all-N47 or whole-project completion.
Baseline main: 9ea592a041965ce5d4ca0d8720908d697b956157. Windows-native Qbrain only.

## Concrete slice of N47

The historical facts table is already used by old chronicle/dream operations.
Do not replace it or copy the earlier unimplemented schema literally. Add a lazy,
versioned SQLite module with memory_fact_module, memory_facts,
memory_fact_evidence and memory_fact_relations. A first successful explicit fact
write backs up an on-disk database before additive initialization. Existing reads,
ordinary startup, the old schema_version and old facts stay unchanged.

Implement a C++ FactStore plus local fact commands and actions behind the existing
memory_read/memory_write MCP gates. No new tool names or broader source/write
permissions. Initial claims are exact COMPLETE extracted user-message quotes:
subject=user, caller-assigned predicate, object copied from validated evidence.
No model inference, substring-to-positive-fact conversion, invented confidence or
automatic truth promotion. Mark outputs untrusted/caller-attested, confidence null.

Allow explicit create, same-quote evidence attachment, retract, supersede and
contradiction edges. Supersede/retract use an expected revision. Only same-source,
same-subject/predicate live claims can be linked; different values do not imply
automatic semantic contradiction. Keep prior versions unless privacy deletion
requires removing them. Superseding evidence loss never automatically revives an
old claim. This is the storage/explicit-lifecycle slice, not all of N47.

## Evidence and privacy invariants

Before creation and every read, validate item/event/source/page joins, extracted
status, both expirations, page liveness, hashes, original whole message and user
role. Evidence attachments pin item, quote and transcript identities. Re-check
inside the write transaction; no model or network I/O occurs under it. Direct
DB mutation capable of recomputing every hash is outside this local integrity
model; do not describe hashes as a signature or multi-user authorization.

Evidence has foreign-key cascade to memory_items; removing the final evidence
removes the claim and relation copies by SQLite trigger, including when the old
memory forget operation runs. Requiring foreign_keys=ON prevents silently broken
cleanup. Soft-deleted/expired/tampered evidence must disappear from reads even
before physical cleanup. No raw-archive fallback, implicit capture, external model
consent, recurring job or persistence of secrets. Keep maximum evidence/relation
counts, candidate count and output-byte bounds explicit.

## Falsifiable acceptance

- Legacy tables/data/schema_version remain; reads do not initialize/write. Lazy
  backup + atomic initialization, idempotence, unsupported version, failure rollback.
- Exact quote/role/item integrity; absent, unextracted, wrong-source, expired,
  edited, soft/hard-deleted evidence; forget deletes last support without revival.
- Idempotent create/attach; multiple supports, explicit relation/supersede/retract,
  stale revisions, cycles, source crossing, atomic rollback, bounded lock waiting
  and independent connections doing concurrent writes.
- UTF-8, NUL/size/input-key checks, no secret echo, output budget, evidence caps.
- Real CLI and MCP defaults/allowed-source/write policy; old six-tool names and
  existing memory behavior remain. Register one additional native unit group and
  require its exact source/EXE-bound process evidence before packaging.
- Existing Windows full suite and current transport/CJK/queue checks remain.
  Separate local sanitizer evidence from native Windows evidence; no live model.

Rollback of code leaves the new tables ignored by older binaries. Physical removal
of additive tables or restoration of a backup is an explicit maintenance action,
not an automatic downgrade. Backups/WAL can retain data; forget is not secure erase.
N47 semantic extraction, conflict inference, scoring/decay and automatic recall
integration remain future work. This node adds actual storage and usable actions.
