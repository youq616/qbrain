# Byte-order marker follow-up

The same separate self-review tested a BOM directly before the first canonical
table header. UTF-8-sig decoding removed the marker and accepted 104/4 rows;
the original native parser saw 0/4. The checker now uses raw UTF-8 decoding,
retaining the marker so the missing canonical header is rejected. No product
or native parser was changed. A real CLI regression covers both normal Python
and -O. Final local checker tests: 19/19 in each mode. This extends NEWLINE-REVIEW.md;
that document's 18-test result is an earlier checkpoint, not the final count.
Final native acceptance and publication remain pending until actual fixed runs.
