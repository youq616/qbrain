# N47V metadata-failure fixture review and correction plan

2026-09-19. Same coordinator, separate owner-authorized review; not another agent.
Second fixed run35449605448 reached78 passing native assertions on both shells
but rejected the harness's expected sharing error. Downloaded PS5 artifact
10586218955 (2752bytes, SHA256 b14197ea9ef232fba18d7859166a1f51b61cb7a83cf39dd57ac96a235a4ba198)
records the failure. This is not yet a final native PASS; later suites were skipped.

The native product opens FILE_READ_ATTRIBUTES only. Microsoft's CreateFile
reference explicitly states attribute requests are not affected by dwShareMode.
An exclusive metadata handle therefore does not imply an inability to verify
case flags. Requiring an error here tests the wrong contract; do not increase
product access rights solely to manufacture that error.
https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilea

Approved correction: preserve all78 existing feature assertions, positively test
metadata-only access while the sharing handle is held and unchanged fixture
state. Then use a test-only Get-Item wrapper to delegate to the original cmdlet,
retain its returned directory attributes, delete only an empty dedicated fixture,
and return that just-observed metadata. The unchanged product must perform its
real native handle query and refuse the disappeared directory. Count exactly one
interleaving, verify the error, restore only that test fixture and compare all
file/directory bytes before/after, then require normal Status to work. No product
hook or test flag, no directory-case caching and no data writes as query probes.

The last three invalid sharing expectations are replaced by six tests covering
both documented sharing compatibility and a real OS metadata-open failure under
explicit deterministic interleaving:84 total assertions. Update exact verifier
names/counts, retain old reports and original installation/recovery suites, then
rerun both native shells and all gates. This is not adversarial concurrency stress
or a new security guarantee. Production installer stays byte-identical.
