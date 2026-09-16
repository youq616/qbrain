# N47G plan engineering review

Reviewer: ChatGPT, separate owner-authorized plan pass. Verdict: PASS for this
implementation scope; actual code and outcome evidence still pending. Not an
independent subagent or third-party review.

The main failure risk is accidentally implementing a loop of independently
committing single-item operations. The plan explicitly requires one transaction
for the complete policy batch and a failure injected after the first write.
A read preview must be unable to become a write through payload fields; routing
must pass the apply flag internally and reject it in JSON. Apply must revalidate
after preview and after optional schema preparation, without sharing cached
supports across those snapshots. Read-only preview must not invoke transaction
control SQL or initialization. Existing N47F limitations remain explicit.

Bound request, evidence work, output and batch size; no implicit truncation or
best-effort skipping of invalid members. Reject duplicate IDs and duplicate JSON
keys to avoid ambiguous selection or operation. Source lives in the existing
resolver, not each member, so one batch cannot broaden scope. Normal input needs
no user quotation in receipts or extra private log. Parser tests include raw key
duplication and wrong types in both preview and apply paths.

Preview is advisory, not a lease or authenticated plan. Current revisions and
fresh complete evidence must still be checked for no-ops. Unsupported, forgotten,
retired or expired assertions cannot be restored by batching. Archived neighbors
still supply counter-evidence. Do not claim archival erases data or that metadata
age proves facts are true/false. No model call or new consent is introduced.

P0/P1 design blockers: none after the explicit atomicity, routing and revalidation
requirements. Tests must independently query policy and revision state, not just
trust success receipts. SQL-trigger rollback and separate-connection races are
required before acceptance, with all old tests retained. Missing Windows or
sanitizer evidence is reported, not replaced by a self-review verdict.
