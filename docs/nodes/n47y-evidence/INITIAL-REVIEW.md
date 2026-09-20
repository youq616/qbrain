# N47Y implementation checkpoint, native acceptance pending

The public-CLI plus named SQL-corruption control reproduced the defect on the
retained Linux product. Its receipt header blob fb33a0fc and page header ec3ef0b0
are identical to current main. Normal application writes were not implicated.

A shared typed reader now serves summary/page and transactional writes. An initial
implementation used TEXT/BLOB IN variants in the same ordered query; EXPLAIN showed
an avoidable temporary ORDER BY tree. Split indexed alias-existence probes from
the single-prefix ordered scan to preserve the early4097 sentinel without sorting
an arbitrarily large malformed set. Four no-sort index-plan checks were added.
This optimization is not a measured end-to-end performance or large-scale guarantee.

Final local GCC executable passed123 checks/156 calls, including original-control
failure,14 corruption variants through5 routes, full data/schema/backup snapshots,
healthy byte-compatible read results/cursors, concurrent cases and natural expiry.
All468 raw streams were checked.14 report mutations reject in normal/optimized
Python. The prior local implementation also passed unchanged75 usage and71 page
checks and4 focused CTest groups; final native CI must rerun those exact gates.

The first offline checker incorrectly assumed every stderr was empty. The inherited
MCP service emits a fixed ready/shutdown banner. The checker now requires exactly
that banner only for the two expected serve commands, with exact LF/CRLF handling;
all raw bytes remain hash-bound. It does not ignore arbitrary stderr. This was a
checker assumption, not a product failure or relaxation of an old test.

Windows baseline is the pinned public N47X EXE. Linux CI freshly builds fixed main
ad31f404 separately, checks its clean Git identity and confines its EXE to that build
root, rather than depend on an expiring historical Actions binary. Logs and binary
hashes record this separate source, not a compiler-reproducibility assertion.

Only two receipt headers change in inherited production source. No default, public
API, schema, installer, Hook or Release change. The same coordinator will separately
review final native artifacts; no native or full-stage PASS is claimed here.
