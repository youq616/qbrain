# N47R additional upgrade review

The approved N47R plan requires actual upgrade and extraction coverage. The
existing five installer suites exercise reinstallation, but not necessarily an
old public package path upgraded to this newly integrated path. Add the missing
explicit old-to-new test; retain the existing suites without changes.

Run the exact first extraction block of the SHA-pinned guide in an isolated
Unicode/space/quote directory under native PowerShell5.1/7. Verify wrong checksum
and existing-output refusal, and the exact EXE/installer extracted by Expand-Archive.
Install the old preview, capture a synthetic user fact through its Hook, switch
to the integrated installer/executable path, and verify configuration ownership,
no duplicate event groups, preserved quotation/fact identity, explicit opt-ins,
default-off reinstall, uninstall retention and unchanged global-default fixture.

This is supplementary source only: the bundle builder/guide/component bytes and
its expected ZIP hash are unchanged from 9e9a92b0. Both fixed-source workflow
results must be checked, never pretend they are the same source commit. The new
37-check test is not yet executed at this planning point; no native PASS claimed.
Reviewer: same coordinating assistant in a separate engineering pass, not another
agent. No signed-in client, actual user data or model-provider request is involved.
