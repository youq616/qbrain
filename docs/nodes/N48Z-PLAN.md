# N48Z — scoped recursive directory CLI search

Base: e0a27f829d970c24ed8c566023ada0911c0042b3.

This addresses the remaining N45 directory-recursive search requirement at the CLI surface without modifying active PR61–67 candidates.

`qbrain search --uri qbrain://source/{resources,skills,memories}/directory/ ...` recursively includes descendants by exact UTF-8 slug prefix. Source, namespace, deleted state and prefix are checked before lexical/vector ranking. Without `--uri`, the old search call path remains unchanged.

The implementation scans one resolved source+namespace and applies exact byte-prefix filtering before scoring. This is a correctness feature, not an index/ANN or throughput claim. It does not add MCP/remote semantics and therefore does not loosen existing remote source authorization.

Acceptance: source/namespace isolation; docs/ must not match docs-neighbor/ or case variants; nested and UTF-8 descendants; deleted pages excluded; >500 out-of-scope matches cannot crowd out scoped lexical results; vector candidates obey the same scope; malformed/non-directory URIs fail; limit/mode behavior; actual Windows/Linux CLI processes; unchanged context/Hook/memory regressions; ASan/UBSan. No real user DB, paid model, merge, deployment or package.
