# Reproducing the N47I supplemental parser review

The frozen product is093088165315b8bc874bfd9ac934efbd4d101f87, tree
b80eeb785a9981bf761ebd3732483285d46146d6. Use that source, not a moving main.
The outcome-only `parser_oracle.py` and its original JSON result are stored here.
They are not runtime dependencies, additional installed commands or a user-machine
task. No real brain, client, model gateway or credentials are required.

Build the original CMake target `qbrain_strict_json_tests`. Its `--parse-lines`
mode uses the same production parsing helper at a1MiB/depth32 budget and returns
only one accepted boolean per raw input. In a fresh source checkout run:

```text
python -B docs/nodes/n47i-evidence/parser_oracle.py --binary <path-to-qbrain_strict_json_tests> --report <new-report.json>
```

The Python side independently retains object pairs instead of allowing dict
construction to erase duplicates, recursively checks scope/decoded Unicode/depth,
and rejects nonfinite numeric, invalid UTF8 and raw-NUL input. A fixed seed makes
all7,781 inputs and the input-stream hash reproducible. The verdict is finite
implementation agreement, not a proof for every possible JSON text. This oracle
uses a test-specific byte cap; public routes have their own documented caps.

The recorded execution used GCC14.2 on Linux, process exit0,4,028 accepted and
3,753 rejected. The script reports executable/script/input hashes but no invented
Git HEAD; original code identity was separately checked by archive reconstruction.
Windows/Server2022/ASan CI results are separate evidence.

`mutation-summary.json` records two deliberately broken temporary helper copies.
Replacing only `!objects.back().insert(value.get<std::string>()).second` with
`false` disables duplicate rejection. Replacing only
`raw.find('\0') != std::string_view::npos` with `false` disables raw-NUL rejection.
Each was compiled with a minimal line-oriented caller using the same include files,
then given this identical oracle corpus. Expected results: oracle exit1 with3,630
and1 mismatches respectively. Neither mutation changed the product header or libs.
Do not use either mutated helper in an application.

`old-negative-final.json` is an intentionally FAIL report from running the final
frozen public process suite against the old baseline binary. It stops on duplicate
capture accepted with exit0 when exit1 was required. Its null source_commit reflects
an archive-only local directory; old binary identity and runtime source are recorded
in `baseline-reproduction.json`. Do not count these expected negative executions
as successful native57-group runs or real authenticated-host acceptance.

`parser_stress.py` uses the same --binary/--report invocation contract and original
parser executable. It checks48 finite wide/deep/recovery inputs; its original
result is parser-stress.json. Intended excessive depth is rejected, not processed
to its full nesting. Both scripts are supplementary review tools, not new CI
product targets or a request for a local-agent task.
