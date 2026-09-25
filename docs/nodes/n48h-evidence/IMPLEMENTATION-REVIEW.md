# N48H implementation and separate review corrections

2026-09-22. Coordinator's separate engineering self-review, explicitly requested
by the owner; not a separate subagent or third party. Before native acceptance.

The initial reference tests passed normal protocol cases. A separately constructed
Responses stream then demonstrated a real consistency gap: response.created usage
reported input_tokens=100, but terminal usage set input_tokens=null and total_tokens=20.
The first standalone accounting dispatcher returned success. Final code retains
observed numeric lower bounds across null updates and rejects that contradiction.
It only constrains currently reported aggregates: an old total is not presumed to
remain the current total when later fields advance. Both sequence origins0/1 and
exact increments follow the previously approved continuation amendment.

A second direct process probe against the first complete local Qbrain build showed
that a final Anthropic message_delta with usage:null reused earlier input/cache
counts and output25 and marked usage_complete=true. Final code treats an explicitly
null usage object as unknown, not 'no update'; absent usage remains no new update.
Initial output alone also never becomes final output. Lower-bound history is still
retained. Original failed input/output files and local binary hashes are preserved
for final evidence; these are synthetic local reproductions, not customer incidents.

Partial nested TTL updates now merge before the unchanged N48G validator checks the
result. Unknown fields and impossible quantities still reject. The first decreasing-
output test hit the old usage_inconsistent check because its unchanged thinking
subtotal exceeded the new parent count. The fixture now isolates monotonicity by
removing that separate contradiction, retaining rejection tests for both conditions.
No production arithmetic or inherited test was weakened.

Final local full-product tests:187 checks/171 commands/513 raw streams in normal
and optimized Python, plus37 direct C++ checks; six unchanged core/batch CTest
targets pass. Additional evidence mutation tests reject15 corruptions. These are
Linux results only; Windows/native source acceptance and final review remain pending.
There is no provider call, file/database mutation, model response or new release.
