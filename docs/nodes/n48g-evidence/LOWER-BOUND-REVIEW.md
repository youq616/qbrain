# Separate outcome review finding: partial counters still impose lower bounds

2026-09-22. Coordinator's separate owner-authorized engineering review, not a
subagent or third party. The first local candidate passed227 planned checks, then
two separately constructed provider objects exposed a real validation omission.

When input_tokens is unknown, cached_tokens=30 and cache_write_tokens=20 cannot
coexist with total_tokens=5 and output_tokens=0. Likewise, known reasoning_tokens=40
cannot coexist with total_tokens=5 and input_tokens=0 merely because output_tokens
is missing. The candidate returned success for each inconsistent object. Saved
actual requests/results identify old local binary4c13a8f2046a2b57ff7291a95709c4fc01435cf87b9669e38de8553d27c4b70c.

Approved correction within the original consistency requirement: compare the total
against independently known input and output lower bounds, without filling unknown
billing buckets. Input lower bound is known input or the sum of known disjoint
cache counts. Output lower bound is the maximum of inclusive output and its known
subcategories (not a sum of potentially overlapping categories). Reject inconsistent
reports, keep all original tests and add both negative cases to direct/CLI tests.
No provider calls, price changes or modification of N48F arithmetic. Initial failed
reproduction must be retained; final tests must run against rebuilt product bytes.
