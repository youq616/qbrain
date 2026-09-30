# N48Z separate preimplementation review

Reviewer: owner-authorized coordinator self-review, not non-author certification.

Repository code/branch/PR search found no scoped recursive directory CLI search. Existing search/think expose source scope only; qbrain:// directory URIs are currently context list/read/summary inputs. N46C exact Top-K and N48V query-vector cache do not provide this function.

Rejected:
- fixed global-source search followed by filtering, because out-of-scope hits can crowd out descendants;
- edits to handlers.cpp/main.cpp or any active PR61–67 candidate path;
- storage-contract changes while separate storage work remains active;
- an MCP feature before CLI scope semantics are validated.

Chosen: separate search-layer implementation plus existing CLI parser. It streams only the selected source+namespace from storage, applies exact recursive slug-prefix membership before ranking, and leaves unscoped search untouched.

PASS to implement and execute focused native tests. Full release integration, real PG and user-client acceptance remain separate.
