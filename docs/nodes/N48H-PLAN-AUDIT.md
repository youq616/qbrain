# N48H separate plan review

2026-09-22. APPROVED for the bounded complete-SSE replay module.
Reviewer: coordinating ChatGPT, separate owner-authorized engineering review,
not another agent or third party. Current owner explicitly requests self-review.

The gap follows N48G: actual streams cannot safely be fed to a nonstream importer.
A proper module must distinguish content deltas, interim usage and final counters,
not merely search for the last usage key. Completion and response identity are
prerequisites; absence of usage must remain unknown. The three state machines
and explicit SSE parser are within a pure native-C++ boundary with no credentials.

Risk review: duplicate stream tails, model/source mixing, lost frames, stale usage,
initial Anthropic output mistaken for final, nonzero tool charges/advanced shapes,
raw response disclosure, malformed data hidden in ignored events and overflow.
The plan retains strict original N48F/G accounting and authorizes no pricing guess,
no live API/network call and no semantic content certification. Source documentation
is current primary evidence, not synthetic tests claimed as provider traffic.

Official references checked2026-09-22:
https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events
https://developers.openai.com/api/reference/resources/responses/streaming-events
https://platform.claude.com/docs/en/build-with-claude/streaming

Chat's usage chunk has empty choices and stream interruption may omit it; Anthropic
message_delta usage is cumulative. Responses supplies terminal typed response
objects. The implementation must test these differences independently. Strict
missing-terminator/unknown-event rejection is deliberately narrower than a general
future-proof rendering client. Final acceptance requires actual fixed-source native
results plus a separate outcome pass; do not infer Windows success from Linux.
