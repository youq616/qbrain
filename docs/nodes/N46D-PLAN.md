# N46D — bounded, atomic embedding response validation

Status: approved after N46D-PLAN-AUDIT.md; outcome pending. Baseline: youq616/qbrain @ 93f80b64756ee520885d8d890bfecfc36eb6af7f.
Scope: Windows native Qbrain only. Continue the owner-approved, disclosed ChatGPT
review workflow used in N46B/N46C; do not claim Claude Code or independent audit.

## Defects and deliverables

The text wrapper currently sizes output using provider-controlled indices and
accepts missing/duplicate entries and heterogeneous or non-finite vectors. Parser
exceptions can echo response data into persisted job errors. Image responses are
checked against 2 MiB only after the shared 8 MiB download and may return a partial
vector on failure. Fix these boundaries before extending embedding provenance.

Implement one internal parser shared by text and image paths. Allocate only the
requested batch count; validate exact count, integral nonnegative unique indices,
nonempty equal dimensions, finite float32-representable numbers and nonzero norm.
Text dimensions, when explicitly requested, must match. Single-image responses
may omit index for compatibility, but a supplied index must be zero. Return no
vectors unless every item passes. No raw parse exception or provider text in errors.

Application limits (not provider API maxima): batch <=2048, dimension <=32768,
aggregate vector components <=1048576, JSON nesting <=16, bounded parse events,
128 object keys per object, and existing byte caps. Bound request serialization
before duplicating/escaping text or Base64; explicitly request float encoding.
Apply the image 2 MiB cap while receiving, not after reading the body.

Repair N42's test-only adapter (missing canonical_source_id/bind_null/links.id)
which now fails on main after N46C. Run that focused suite within the main native
validation workflow too, rather than leaving it as a disconnected stale check.
Do not change production source identity rules to satisfy a test stub.

## Acceptance

1. Pure C++ tests: valid reordered batches; negative/extreme/fractional/duplicate
   indices; empty/missing/extra data; malformed/deep/oversized/duplicate-key JSON;
   dimension mismatch; float overflow, non-numeric and zero vectors; no partial
   output or private sentinel echo. Deterministic permutation/mutation properties.
2. Windows loopback exercises real embed_texts/embed_image and shared WinHTTP.
   Check exact request encoding, no-credentials/invalid-input no-network paths,
   invalid 2xx, HTTP errors, truncated bodies, image caps and valid Unicode.
3. A real SQLite embedding job receiving a malformed batch fails without updating
   any chunk. A correct reordered batch writes the right vector to each chunk.
4. Register group 47 and update explicit packaging gates; an old 46-group log
   cannot pass. Preserve HTTP/memory/context/MCP/hooks/PowerShell checks and N46C.
5. Run fixed-input portable and Windows tests, save exact commit-bound evidence;
   no passing or merge claim before real outcomes. Disclose any existing failures.

## Compatibility, security, rollback

No schema migration, credentials, paid provider calls, new services, MCP operations,
implicit provider consent, database cleanup or changes to configured model identity.
Mock output dimensions remain test-specific. No cross-provider/model provenance
or semantic-quality guarantee: finite vectors do not prove the intended model ran.
Oversized batches should be split by callers; no automatic retry that incurs cost.
Rollback is a code/test/build revert, not a data-format migration. Work on an
isolated optimization branch; retain main until reviewed native acceptance.
