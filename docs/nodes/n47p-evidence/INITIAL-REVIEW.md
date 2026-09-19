# N47P initial checkpoint and review findings

Initial candidate fbfc6e971630fda766b7d64ee1c83d57e578e09f ran35412963277.
Windows PowerShell5.1 job105816042402 failed before any new recovery case because
PSScriptRoot was empty while evaluating the optional Installer parameter default.
This is a test harness startup failure, not evidence of product passage/failure.
Move that default resolution into the script body; retain every original case and
rerun both shells. Original failure artifact10575120542,614bytes, SHA256
dad1fd3c641f280576c5d1f9bc76798c4caac2651dfd4a5af09e4837de9bd86f.
Other initial job outcomes must be recorded separately; no pending gate is PASS.

A separate code review identified another decoding boundary: PowerShell7 can
enumerate a one-element root JSON array into a scalar object. Recovery must require
an object envelope before ConvertFrom-Json; the new top-array case covers both
shells. Normal client configuration parsing is not changed. Reference for array
enumeration: MicrosoftDocs/PowerShell-Docs ConvertFrom-Json / NoEnumerate.

No C++/schema/consent/default option or native assertion changes. Only the test
startup and journal root-shape boundary change; tests grow from58to60 cases, not
by removing the failing harness or relaxing product checks. This checkpoint is not
an outcome audit or native acceptance.
