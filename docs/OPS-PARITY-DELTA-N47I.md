# N47I operation delta

Actual tested source093088165315b8bc874bfd9ac934efbd4d101f87, tree
b80eeb785a9981bf761ebd3732483285d46146d6. Scope: public JSON ambiguity rejection,
not another memory feature, new permission or full-system parser replacement.

Ordinary memory capture and fact payloads now share per-object decoded-key
uniqueness with explicit raw-byte/depth bounds. Batch duplicate errors remain.
MCP envelopes reject ambiguous input before dispatch with a fixed null-id parse
error; incoming Hook events reject before runtime state/capture. Valid sibling
objects and JSON text inside strings retain meaning. Raw NUL cannot terminate
parsing early, while escaped string NUL is validated by the normal field rules.

No schema, new tool name, installer default, provider call, truth score, automatic
aging or source permission changes. Existing stored transcript/config parsers are
out of scope. Normal unique-key input within documented bounds continues to work;
ambiguous or over-depth clients intentionally receive a rejection rather than
silently choosing one repeated value. A caller's prior core startup is not newly
claimed write-free by inner-operation rejection.

Registry now requires57 named native groups. New tests bind actual unit11/95 and
raw CLI/MCP/Hook process54/39 results to the same source, executable and scripts.
Outcome review includes independent generated-input agreement, deliberately broken
parser copies and finite wide/deep recovery checks. See N47I-HARD-AUDIT.md for
original native evidence, retained local aggregate failure and exact limitations.
