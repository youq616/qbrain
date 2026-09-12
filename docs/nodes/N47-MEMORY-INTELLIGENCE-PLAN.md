# N47 — Memory Intelligence Layer

Status: planning and implementation start.
Baseline: qbrain main after N46D queue reliability work.
Scope: Windows native Qbrain memory engine.

## Objective

Move Qbrain from storage-oriented memory into evidence-backed long-term memory management.

The goal is not to blindly store more conversation. The goal is to maintain reliable facts, preferences, conflicts and lifecycle states with evidence.

## N47.1 Fact Graph

Introduce a fact layer between raw evidence and user memory.

Model:

```
Conversation
    |
    v
Evidence
    |
    v
Fact
    |
 +-- confidence
 +-- source_count
 +-- created_at
 +-- verified_at
 +-- conflict_group
```

Requirements:

- Never replace historical evidence silently.
- Preserve original source references.
- Support multiple versions of the same fact.
- Allow rollback and explanation.

## N47.2 Conflict Engine

Detect contradictory facts:

Example:

```
Fact A:
location = Korea

Fact B:
location = China

State:
CONFLICT
```

Resolution factors:

- user explicit correction
- timestamp
- evidence quality
- number of independent confirmations

## N47.3 Memory Decay

Add lifecycle scoring:

```
memory_score =
 confidence
 * freshness
 * verification
 * usage
```

Low-value stale memories should reduce retrieval priority without deleting evidence.

## N47.4 Dream Consolidation

Upgrade background processing:

```
raw memories
 -> duplicate detection
 -> conflict analysis
 -> fact consolidation
 -> compression
```

No automatic destructive cleanup.

## N47.5 User Model

Separate stable preferences from temporary facts.

Examples:

Preference:
- prefers command line workflows

Temporary state:
- currently using Windows

## N47.6 Memory Firewall

Prevent unsafe memory writes:

Risk levels:

LOW:
 automatically store

MEDIUM:
 require evidence

HIGH:
 reject automatic persistence

## Acceptance requirements

- Existing N46D retrieval, queue and embedding tests remain unchanged.
- No silent migration of existing memories.
- Every new fact must preserve evidence lineage.
- Add native Windows regression coverage before merge.
- No claim of complete gbrain/OpenViking equivalence until independently measured.

## Current implementation order

1. Fact schema abstraction.
2. Evidence-to-fact extraction interface.
3. Conflict storage model.
4. Retrieval scoring integration.
5. Dream consolidation worker.
6. User preference layer.
7. Memory firewall.
