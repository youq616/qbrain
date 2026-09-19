# N47O first read-only CI failure

Run 35410588581, commit d8258ae88b9d5c0c7c654964655a77e6a2939a5e,
job 105809285667. Both ordinary/optimized 14-method suites passed. Source/review
checkout, PR and fixed run checks passed up to the first original artifact request.
The request actions/artifacts/10557946121/zip failed; no tag or release was created.
The initial client suppressed HTTP details, so its exact server status is unknown.

Inspection found the client applied the release-asset octet-stream Accept header
also to Actions ZIP endpoints. Official Actions docs specify the ordinary REST
Accept for the download redirect. The fix restricts the special binary Accept to
release-asset paths, adds safe HTTP-code-only errors (no tokens or signed URLs),
and adds two regression methods without removing the original 14 methods.
This is a source fix awaiting a fresh full read-only run, not a retroactive PASS.

Retained original artifact: 10574556542, 5276 bytes, SHA-256
0cd18051e208f28ea18e863b87b0fbf2c02faa4b7a054e9e0c39276a7f2ffb54.
No change to product, original artifact hashes, checks, CI permissions or consent.
Reference: https://docs.github.com/en/rest/actions/artifacts#download-an-artifact
