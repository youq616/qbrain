# Embedding response and retrieval contracts (N46D)

Text embedding responses are accepted only as a complete batch: one indexed,
nonempty, finite, nonzero vector per input, with unique integral indices in
range. Reordered complete responses are accepted. Negative, fractional, huge,
duplicate or missing indices reject the batch without returning partial vectors.
Vectors must have consistent width and match an explicitly requested dimension.
Booleans/nulls/strings, float overflow and all-zero float vectors are rejected.
Responses are byte-bounded by transport, and parser nesting is limited to 16.
Local policy limits: 2,048 batch entries, 16,384 dimensions per vector, 1,048,576
numeric vector elements across a response. These are not upstream token limits.

The request explicitly asks for float-array encoding. An optional response model
must match the configured request model exactly, including case. Missing model
metadata retains the request label for compatible gateways. An alias mismatch
is rejected, not guessed or silently relabelled. Request model identifiers must
be printable non-space ASCII, 1..256 bytes. Errors never include parser excerpts
or raw provider response bodies. These rules are not provider truth attestation.

Production `search` and `think` use the shared hybrid path with the active model
label plus the query vector width, in addition to source and live-page filters.
Vectors with absent/different labels or inconsistent stored dimension metadata
are excluded from vector ranking. Their pages are not deleted and remain eligible
for FTS. No automatic re-embedding, model call retry, data migration or permission
change is introduced. Explicit QBRAIN_EMBED_MOCK uses `mock-embedding`; it remains
a synthetic test fixture, not a meaningful semantic model.

C++ clients supplying their own query vectors may set `HybridOpts.embedding_model`
to that vector's known model. An explicit empty label disables the vector lane.
The low-level raw `vector_search` helper retains its legacy unfiltered mode when
no model argument is supplied; user-facing CLI/MCP search does not use that mode.
No additional CLI/MCP flag disables production model checks.

Image embeddings use the same batch validator for one vector. Their 2 MiB body
limit is enforced during transport; text dimension configuration is not imposed
on image vector width. File access remains restricted as before. Image requests
are an existing optional provider extension, not a claim that every OpenAI-like
service accepts image input at /embeddings.

Matching model names/dimensions does not detect different providers or weights
under an identical name. There is no endpoint fingerprint migration, model quality
claim, or automatic repair of legacy metadata. Model aliases and old unknown
vectors may require deliberate re-embedding; that can incur provider costs.

Protocol reference: https://developers.openai.com/api/reference/resources/embeddings
Parser-depth guidance: https://json.nlohmann.me/features/parsing/parser_callbacks/
