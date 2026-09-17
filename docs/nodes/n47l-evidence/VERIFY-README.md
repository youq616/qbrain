# N47L offline candidate evidence verification

`verify_candidate.py` reads downloaded CI artifacts, checks them against an
explicitly pinned GitHub metadata snapshot, validates the fixed candidate source
tree, and revalidates native/portable reports. It never downloads, runs qbrain,
builds, signs, merges, or publishes. A successful result is CI evidence readback;
source-code review and publication authorization are separate decisions.

The implementation uses only Python's standard library. Use Python 3.10 or later.
Report validators are imported only from the byte-authenticated source archive in
a fresh temporary directory and an isolated `python -I -S -B` child process. The
provided `--source` directory must contain all source-archive files with the
original bytes or the single permitted native Windows CRLF checkout transform.
Extra untracked local files are not imported or copied to that temporary tree.

## Required downloads and metadata

The caller obtains GitHub metadata with the GitHub plugin or a separately reviewed
delivery workflow. Collect the full latest-attempt job pages for both workflow
runs and the relevant artifact metadata. Never manufacture a success snapshot
from old runs. Record one normalized metadata JSON object with this shape:

```json
{
  "schema_version": 1,
  "repository": "youq616/qbrain",
  "source_commit": "<40 lowercase hex>",
  "source_tree": "<40 lowercase hex>",
  "runs": {
    "n44": {
      "id": 123,
      "head_sha": "<candidate commit>",
      "path": ".github/workflows/n44-validation.yml",
      "repository": "youq616/qbrain",
      "head_repository": "youq616/qbrain",
      "event": "push",
      "status": "completed",
      "conclusion": "success",
      "run_attempt": 1,
      "html_url": "https://github.com/youq616/qbrain/actions/runs/123",
      "jobs_total_count": 7,
      "jobs": []
    },
    "n42": {}
  },
  "artifacts": {
    "source": {
      "id": 456,
      "name": "qbrain-n44-source",
      "run_id": 123,
      "head_sha": "<candidate commit>",
      "expired": false,
      "sha256": "<64 lowercase hex, remove API sha256: prefix>",
      "size_in_bytes": 12345,
      "file": "source.zip"
    }
  }
}
```

The abbreviated JSON above is explanatory and will fail verification. Each job
must retain `id`, `name`, `run_id`, `head_sha`, `run_attempt`, `status`,
`conclusion`, and its full `steps` list. Every mandatory job and step must have
succeeded in the pinned run attempt. `jobs_total_count` comes from the fully
paginated API response. The metadata verifier requires both complete run entries
and exactly the following artifact pins and outer ZIP filenames:

| Label / filename | Workflow | GitHub artifact name |
|---|---|---|
| `source` / `source.zip` | N44 | `qbrain-n44-source` |
| `windows` / `windows.zip` | N44 | `qbrain-n44-windows-logs` |
| `package` / `package.zip` | N44 | `qbrain-n44-windows-development-package` |
| `server2022` / `server2022.zip` | N44 | `qbrain-n46f-server2022-http-evidence` |
| `portable` / `portable.zip` | N44 | `qbrain-n44-portable-logs` |
| `sanitizer` / `sanitizer.zip` | N44 | `qbrain-n47g-sanitizer-evidence` |
| `n42-windows` / `n42-windows.zip` | N42 | `qbrain-n42-windows-logs` |

Commit/review the metadata bytes and fix their SHA-256 in the delivery invocation.
The hash is an external trust input; JSON plus a newly calculated hash is not a
GitHub signature. This verifier does not requery GitHub. Before an actual
publication, the caller must also requery and compare the immutable candidate,
run/attempt/job and artifact identities to the reviewed snapshot.

## Invocation

```text
python -I -S -B verify_candidate.py --source <exact-candidate-directory> --artifacts <outer-zip-directory> --metadata <metadata.json> --metadata-sha256 <fixed-metadata-sha256> --source-sha <candidate-sha> --source-tree <candidate-tree> --n44-run <N44-id> --n42-run <N42-id> --report <new-output.json>
```

`--report` must be a new path. On a failure the command exits nonzero without a
success report. The JSON output records actual validator-returned N47L and older
report counts, both independently matched 60-group native registries, exact
original product ZIP and EXE hashes/sizes, source file count, artifact IDs, and
all executed readback checks. Package inventory is extracted from the fixed
source packaging script with AST; new declared dependencies are included without
hardcoding the former 72-member inventory. Manifest JSON, source attachments,
and original Windows report bytes are all cross-checked.

The unit and HTTP probe executables are not separately present in these CI
artifacts. Their report hashes are structural attestations, not independently
rehashed probe binaries. The output explicitly retains that limitation and the
unverified signature, live host/model consumption, and PostgreSQL integration
scope. Server 2022 covers HTTP and unit suites, not the full CLI/MCP process suite.

## Verifier regression checks

The optional `test_verify_candidate.py` accepts the same real fixture inputs:

```text
python -B test_verify_candidate.py --metadata <metadata.json> --source <candidate-directory> --artifacts <outer-zip-directory>
```

Its 14 tests exercise a genuine positive fixture and mutations of workflow
source/attempts, metadata/artifact digests, source tree, missing native groups,
joint ZIP/manifest deletion, report byte mismatch, inconsistent production
binary hashes, duplicate/nonfinite JSON, unsafe ZIP paths/aliases and modes, and
dynamic literal packaging inventory. They do not execute the product. Counts
from a historical fixture certify the verifier test only, not a new candidate.
