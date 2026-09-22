# N48G separate plan review

2026-09-22. APPROVED for the bounded provider-response import module.
Reviewer: coordinating ChatGPT, separate engineering plan review explicitly
requested by the owner; not a subagent or third-party audit.

This advances N48F from hand-normalized counts to usable response import. Preserve
its exact arithmetic and default brain-free CLI. Main risks: cached-token double
counting, treating missing fields as zero, rebilling one response, accidental text
exposure, partial stream totals, model/rate mismatch, and unrepresented TTL/audio/
iteration charges. The bounded strict adapter and explicit exclusions address each
without broadening write authority. A malformed member must reject the whole batch.

Primary contracts checked2026-09-22: OpenAI official prompt-caching and API usage
reference show inclusive total input with cached_tokens/cache_write_tokens and
inclusive output; Anthropic official Messages reference treats ordinary input,
cache creation and cache read as separate. Anthropic output details are decomposition,
not extra output. Mixed TTL input cannot use a fabricated single write rate. Missing
optional fields remain unknown; historical omission does not authorize a zero guess.

Sources: https://developers.openai.com/api/docs/guides/prompt-caching ;
https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create ;
https://developers.openai.com/api/reference/cli/resources/responses/methods/create ;
https://platform.claude.com/docs/en/api/typescript/messages .
No model request, real invoice, price quotation or external consumption is inferred
from these documented contracts. Final review must inspect actual independent
results, not just the existence of tests or a successful old workflow.
