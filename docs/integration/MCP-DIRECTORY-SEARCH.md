# Directory-scoped MCP search

N49D candidate capability. Native qualification and outcome acceptance are
pending for this source tree. This does not establish real-client consumption,
model quality, PostgreSQL directory support, or release readiness.

The existing `search` tool accepts an optional directory `uri`. It recursively
searches descendants of that directory within the source already selected and
authorized for the request. Both the full and six-tool memory profiles expose
the same argument; no tool is added.

## Example

For a client whose `alpha` source is already authorized:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "search",
    "arguments": {
      "query": "release checklist",
      "source_id": "alpha",
      "uri": "qbrain://alpha/resources/docs/",
      "no_vector": true,
      "limit": 10
    }
  }
}
```

This can match `docs/checklist` and `docs/releases/checklist`, but not
`docs-neighbor/checklist`, `Docs/checklist`, another namespace, another source,
or a deleted page. Directory and page paths are matched as exact UTF-8 prefixes.

Supported namespaces are:

- `resources`: pages other than skills and session fragments
- `skills`: pages whose type is `skill`
- `memories`: pages whose type is `session_fragment`

A namespace root such as `qbrain://alpha/resources/` includes every directory in
that namespace. Every directory URI ends in `/`. Percent encoding, traversal
components, duplicate separators, query strings, fragments, and backslashes are
not accepted. Unicode names can be supplied directly as valid UTF-8 JSON.

## Source and compatibility rules

The URI narrows the existing effective source. It never selects or authorizes a
different source. Existing explicit `source_id`, `QBRAIN_SOURCE`, default-source
selection, canonicalization, and `mcp.allowed_sources` behavior are preserved.
Use the canonical source spelling in the URI. For example, a request resolved to
`default` cannot switch to `alpha` just by supplying an alpha URI.

Omitting `uri` preserves the existing hybrid-search path. When present, URI must
be a string; null, an empty string, and malformed values are rejected rather
than treated as omission. Well-formed tool arguments receive bounded URI/source
errors without echoing the submitted value. Malformed JSON or UTF-8 in the
envelope retains the existing JSON-RPC parse error.

The existing limit, mode, rerank, and no-vector controls remain available.
`no_vector` controls query embedding; it does not change directory membership.
The returned rank, source ID, page ID, slug, title, score, rerank score, and
snippet fields are unchanged. A valid directory with no matches succeeds with
the existing empty-results response.

Source authorization and URI validation complete before embedding/provider
work. The existing default-deny write policy is unchanged. Actual loopback HTTP
MCP is a Windows-native transport and retains its token requirement; Linux HTTP
stubs are not transport acceptance evidence.

## Validation scope

The candidate is required to pass ordinary synthetic SQLite functional tests,
same-source CLI/MCP result comparisons, actual stdio on Linux and Windows,
authenticated loopback MCP HTTP on both Windows build paths, the listed legacy
regressions, both Windows canonical suites, and ASan/UBSan. Required source,
binary, command, and raw-output evidence is bound to the exact frozen candidate.

See [N49D plan](../nodes/N49D-PLAN.md) and
[outcome status](../nodes/N49D-HARD-AUDIT.md). An external acceptance report for a
specific candidate does not grant a later modified tree the same qualification.
