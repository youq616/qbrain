# Windows model HTTP transport boundaries (N46B)

This applies to Qbrain's shared native C++ WinHTTP transport used by chat,
embedding, memory extraction and optional directory summaries. It does not
configure a provider, enable external processing or change MCP write permission.

## Defaults and compatibility

| Boundary | Policy |
| --- | --- |
| Network wait | One steady-clock deadline across send, headers and all body reads |
| Timeout argument | 1..600,000 ms; existing transport default 60,000 ms |
| Response body | 8 MiB default; explicit C++ caller override 1 byte..64 MiB |
| Outbound JSON | At most 32 MiB, checked before converting WinHTTP byte counts |
| Read buffer | Fixed 16 KiB; streamed bodies still checked without Content-Length |
| Response headers | WinHTTP 64 KiB header limit |
| Redirects | Never followed, including same-origin and HTTPS-to-HTTP |
| Automatic credentials/cookies | Disabled; explicit bearer header still supported |
| URL | HTTP/HTTPS only; reject userinfo, base query/fragment and unsafe controls |
| Error output | Status or numeric transport code only, no raw provider body |

A base URL of `https://provider.example/v1/` plus `/chat/completions` is joined
as `/v1/chat/completions`, not `/v1//chat/completions`. Use the final API endpoint
rather than a redirecting gateway URL. Query arguments belong in the explicit
endpoint path, not the base URL. Configure HTTPS for remote providers; HTTP is
retained for explicitly configured local/test services and is not encrypted.

The `chat_complete` wrapper keeps its pre-existing 120,000 ms default and maps
nonpositive wrapper timeouts to that default. Memory extraction passes 60,000 ms.
There is no automatic retry inside this transport. An OS scheduling pause or
handle teardown is not covered by a hard-real-time latency promise. Incomplete,
over-limit and cancelled responses return an error with status zero and no body,
even after receiving 200 headers. HTTP failures retain their status but not their
body. Chat timeout classification now uses the transport's explicit failure kind.

## Cancellation and privacy

Network operations use asynchronous WinHTTP. Callbacks signal completion only;
they never recursively invoke reads. One deadline is used for all completion
waits, including trickled packets. Cancellation closes the request; its callback
context, headers, outbound body and fixed receive buffer stay alive until the
last HANDLE_CLOSING notification. No cancellation thread closes a synchronous
request. TLS certificate validation is left enabled.

Provider errors cannot copy prompts, bearer keys or model text into transport
error strings. This is not a complete application-wide DLP or log audit. It does
not erase private data from process memory, operating-system buffers or backups.

## Tests and scope of evidence

`tests/test_n46b.cpp` checks rejection before network I/O. `.ci/test_http_transport.py`
exercises the actual C++ transport using synthetic loopback fixtures on Windows:
normal/Unicode/exact/oversized/chunked/truncated responses, stalled headers/body,
trickled packets, redirect and automatic-authentication refusal, error redaction,
repeated cancellation, concurrent requests and chat integration. Python is a CI
test dependency, not a required Qbrain runtime or Windows installation service.

The CI package gate requires native transport results from the same source commit
as the tested application. A Linux unsupported-platform stub cannot pass native
HTTP acceptance. Native CI is not a real logged-in Win11 Agent lifecycle test,
a paid-provider test, proxy/PAC coverage or a full gbrain-equivalence claim.

## Design references

Microsoft WinHttpCloseHandle (context survives until HANDLE_CLOSING):
https://learn.microsoft.com/en-us/windows/win32/api/winhttp/nf-winhttp-winhttpclosehandle

Microsoft WinHttpReadData (asynchronous buffer lifetime, callbacks and EOF):
https://learn.microsoft.com/en-us/windows/win32/api/winhttp/nf-winhttp-winhttpreaddata

Microsoft WinHttpSendRequest (outbound buffer lifetime):
https://learn.microsoft.com/en-us/windows/win32/api/winhttp/nf-winhttp-winhttpsendrequest

Microsoft option flags (redirects/authentication/cookies/header limit):
https://learn.microsoft.com/en-us/windows/win32/winhttp/option-flags
