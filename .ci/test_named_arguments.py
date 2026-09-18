"""N47M real-process parser regressions; isolated synthetic SQLite, no providers.

Python is a test dependency only. Reported exits/stdout come from real processes;
this script is not an independent review or a substitute for the native gates.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import tempfile
from typing import Callable


def wire(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    baseline = args.baseline.resolve(strict=True) if args.baseline else None
    checks: list[dict] = []
    commands: list[dict] = []

    def case(label: str, test: Callable[[], None]) -> None:
        try:
            test()
        except Exception as error:
            checks.append({"name": label, "passed": False, "error": str(error)})
            print(f"FAIL {len(checks)}: {label}: {error}", flush=True)
        else:
            checks.append({"name": label, "passed": True})
            print(f"PASS {len(checks)}: {label}", flush=True)

    with tempfile.TemporaryDirectory(prefix="qbrain-n47m-") as tmp:
        root = Path(tmp) / "中文 arguments 😀"
        root.mkdir()
        env = {k: v for k, v in os.environ.items()
               if not k.upper().startswith(("QBRAIN", "OPENAI", "ANTHROPIC"))}
        env.update(HOME=str(root), LOCALAPPDATA=str(root), USERPROFILE=str(root))
        data = (root if os.name == "nt" else root / ".local/share") / "Qbrain"
        brains = ("intended", "environment", "configured", "default")
        events: dict[tuple[str, str], str] = {}
        quotes: dict[tuple[str, str], str] = {}
        bodies: dict[tuple[str, str], str] = {}

        def run(argv: list[str], payload: object = None, *, expected: int | None = 0,
                extra: dict | None = None, executable: Path | None = None,
                stdin: bytes | None = None) -> subprocess.CompletedProcess:
            raw = stdin if stdin is not None else (wire(payload) if payload is not None else b"")
            exe = executable or binary
            process = subprocess.run([str(exe), *argv], input=raw, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, cwd=root, env={**env, **(extra or {})}, timeout=30)
            commands.append({"binary": "baseline" if exe == baseline else "candidate", "argv": argv,
                             "stdin": raw.decode("utf-8"), "exit": process.returncode,
                             "expected_exit": expected, "stdout": process.stdout.decode("utf-8", errors="replace"),
                             "stderr": process.stderr.decode("utf-8", errors="replace"),
                             "stdout_sha256": hashlib.sha256(process.stdout).hexdigest()})
            if expected is not None:
                require(process.returncode == expected,
                        f"exit {process.returncode}, expected {expected}: {argv}: "
                        + (process.stdout + process.stderr).decode("utf-8", errors="replace"))
            return process

        def obj(argv: list[str], payload: object = None, **kwargs) -> dict:
            return json.loads(run(argv, payload, **kwargs).stdout)

        def sql(brain: str, statement: str, parameters: tuple = ()) -> list:
            with closing(sqlite3.connect(data / "brains" / brain / "brain.db")) as db:
                rows = db.execute(statement, parameters).fetchall()
                db.commit()
                return rows

        def config(brain: str, key: str, value: str) -> None:
            sql(brain, "INSERT INTO config(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

        def snapshot(brain: str = "intended") -> str:
            with closing(sqlite3.connect(data / "brains" / brain / "brain.db")) as db:
                tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                state = {table: sorted(db.execute('SELECT * FROM "' + table.replace('"', '""') + '"').fetchall(), key=repr)
                         for table in tables}
            return hashlib.sha256(repr(state).encode("utf-8")).hexdigest()

        def payload(fragment: str, quote: str = "I prefer explicit local consent.") -> dict:
            return {"session_id": "n47m", "fragment_id": fragment,
                    "messages": [{"role": "user", "content": quote}]}

        def memory(argv: list[str], *, brain: str = "intended", source: str = "alpha", **kwargs) -> dict:
            # This helper uses safe order for fixture writes; regressions below supply raw argv.
            return obj(["memory", argv[0], "--brain", brain, *argv[1:], "--source", source], **kwargs)

        def mcp(tool: str, arguments: dict, *, allow_write: bool = False) -> dict:
            message = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": arguments}}
            result = obj(["serve", "--brain", "intended", *(["--allow-write"] if allow_write else [])],
                         stdin=wire(message) + b"\n")["result"]
            require(not result.get("isError", False), f"MCP error: {result}")
            return json.loads(result["content"][-1]["text"])

        for brain in brains:
            run(["init", "--brain", brain, "--no-default"])
            config(brain, "memory.writeback", "salient")
            sources = ("default", "alpha", "--limit", "--brain", "--manual", "--source", "--layer", "--method", "--uri", "--offset", "--revision", "--max-bytes", "--event") if brain == "intended" else ("alpha",)
            for source in sources:
                if source != "default":
                    sql(brain, "INSERT INTO sources(id,name) VALUES(?,?)", (source, source))
                quote = f"I prefer {brain}/{source} with literal --source --brain --limit --max-bytes --manual --query. 中文😀"
                body = f"RAW {brain}/{source}\r\n中文😀 exact page."
                quotes[brain, source], bodies[brain, source] = quote, body
                cap = memory(["capture"], brain=brain, source=source, payload=payload(source, quote))
                events[brain, source] = cap["event_id"]
                memory(["extract", "--event", cap["event_id"]], brain=brain, source=source)
                sql(brain, "INSERT INTO pages(source_id,slug,title,body) VALUES(?,?,?,?)", (source, "docs/first", "N47M raw", body))

        def verify_memory(argv: list[str], brain: str = "intended", source: str = "alpha", extra: dict | None = None) -> None:
            value = obj(argv, extra=extra)
            require(value["source_id"] == source, "wrong source: " + str(value))
            require(len(value["items"]) == 1, "expected one complete memory: " + str(value))
            require(value["items"][0]["quote"] == quotes[brain, source], "wrong brain or raw quote")
            require(value["items"][0]["event_id"] == events[brain, source], "wrong event identity")

        def verify_context(argv: list[str], brain: str = "intended", source: str = "alpha", extra: dict | None = None) -> None:
            value = obj(argv, extra=extra)
            require(value["source_id"] == source, "wrong context source")
            require(value["content"] == bodies[brain, source], "wrong brain or raw page")
            require(value["revision"] == hashlib.sha256(bodies[brain, source].encode()).hexdigest(), "wrong raw revision")
            require(value["provider_calls"] == 0 and value["layer"] == "L2", "raw read semantics changed")

        case("memory --source query cannot retarget source", lambda: verify_memory(
            ["memory", "read", "--brain", "intended", "--query", "--source", "--limit", "5", "--source", "alpha"]))
        case("memory source-first control", lambda: verify_memory(
            ["memory", "read", "--brain", "intended", "--source", "alpha", "--query", "--source", "--limit", "5"]))
        for needle in ("--brain", "--source", "--limit", "--max-bytes", "--manual", "--query"):
            case(f"memory option-shaped query {needle}", lambda needle=needle: verify_memory(
                ["memory", "read", "--query", needle, "--source", "alpha", "--limit", "5", "--max-bytes", "8192", "--brain", "intended"]))
        for source in ("--brain", "--source", "--layer", "--method", "--uri", "--offset", "--revision", "--max-bytes"):
            case(f"context literal source {source}", lambda source=source: verify_context(
                ["context", "read", "--source", source, "--uri", f"qbrain://{source}/resources/docs/first", "--layer", "L2", "--brain", "intended"], source=source))

        # Neither the query nor a source value named --brain may override fallback resolution.
        for label, file_brain, extra, explicit, expected_brain in (
            ("default", None, {}, [], "default"),
            ("file", "configured", {}, [], "configured"),
            ("environment", "configured", {"QBRAIN_BRAIN": "environment"}, [], "environment"),
            ("empty environment", "configured", {"QBRAIN_BRAIN": ""}, [], "configured"),
            ("explicit", "configured", {"QBRAIN_BRAIN": "environment"}, ["--brain", "intended"], "intended"),
        ):
            if file_brain is None:
                (data / "config.json").unlink(missing_ok=True)
            else:
                (data / "config.json").write_bytes(wire({"brain_id": file_brain}))
            case(f"memory brain precedence {label}", lambda extra=extra, explicit=explicit, expected_brain=expected_brain: verify_memory(
                ["memory", "read", "--query", "--brain", "--source", "alpha", *explicit], brain=expected_brain, extra=extra))
            case(f"context brain precedence {label}", lambda extra=extra, explicit=explicit, expected_brain=expected_brain: verify_context(
                ["context", "read", "--source", "alpha", "--uri", "qbrain://alpha/resources/docs/first", "--layer", "L2", *explicit], brain=expected_brain, extra=extra))

        (data / "config.json").write_bytes(wire({"brain_id": "intended"}))
        for source in ("--brain", "--source", "--layer", "--method", "--uri", "--offset", "--revision", "--max-bytes"):
            case(f"context fallback with literal source {source}", lambda source=source: verify_context(
                ["context", "read", "--source", source, "--uri", f"qbrain://{source}/resources/docs/first", "--layer", "L2"], source=source))

        config("intended", "mcp.allowed_sources", "alpha,--brain")

        def parity() -> None:
            cli = memory(["read", "--query", "--brain"])
            require(cli == mcp("memory_read", {"source_id": "alpha", "query": "--brain"}), "CLI/MCP memory mismatch")
            argv = ["context", "read", "--source", "--brain", "--uri", "qbrain://--brain/resources/docs/first", "--layer", "L2", "--brain", "intended"]
            require(obj(argv) == mcp("context_read", {"source_id": "--brain", "uri": "qbrain://--brain/resources/docs/first", "layer": "L2"}), "CLI/MCP context mismatch")
        case("memory/context CLI and MCP preserve exact evidence", parity)

        # Keep parser and operation errors separate, with their existing exact exit contracts.
        before_invalid = snapshot()
        invalid = [
            (["memory", "read", "--query"], 2, "invalid_cli_argument"),
            (["memory", "read", "--unknown", "x"], 2, "invalid_cli_argument"),
            (["memory", "read", "--query", "x", "--query", "y"], 2, "duplicate_argument"),
            (["memory", "read", "--brain", "new-one", "--brain", "new-two"], 2, "duplicate_argument"),
            (["memory", "capture", "--manual", "--manual"], 2, "duplicate_argument"),
            (["memory", "extract", "--event", ""], 2, "event_id_required"),
            (["memory", "status"], 2, "event_id_required"),
            (["memory", "read", "--limit", ""], 1, "invalid_integer"),
            (["memory", "read", "--max-bytes", ""], 1, "invalid_integer"),
            (["memory", "read", "--brain", ""], 2, "invalid brain id"),
            (["context", "read", "--uri"], 1, "invalid_cli_argument"),
            (["context", "read", "--unknown", "x"], 1, "invalid_cli_argument"),
            (["context", "read", "--brain", "new-one", "--brain", "new-two"], 1, "invalid_cli_argument"),
            (["context", "read", "--layer", ""], 1, "invalid_layer"),
            (["context", "read", "--max-bytes", ""], 1, "invalid_integer"),
            (["context", "read", "--offset", ""], 1, "invalid_integer"),
            (["context", "read", "--brain", ""], 2, "invalid brain id"),
            (["context", "summary", "--method", ""], 1, "summary_requires_directory"),
            (["context", "summary", "--source", "alpha", "--uri", "qbrain://alpha/resources/docs/", "--method", ""], 1, "invalid_summary_method"),
        ]
        for argv, expected, code in invalid:
            def invalid_case(argv=argv, expected=expected, code=code) -> None:
                process = run(argv, expected=expected)
                require(code in (process.stdout + process.stderr).decode(), "wrong error code")
            case("invalid " + repr(argv), invalid_case)
        case("invalid input leaves all application rows unchanged", lambda: require(snapshot() == before_invalid, "invalid call mutated data"))

        def defaults() -> None:
            require(obj(["memory", "read"])["source_id"] == "default", "missing source no longer defaults")
            require(memory(["read", "--query", ""]) == memory(["read"]), "empty query no longer means full source read")
            require(obj(["context", "list", "--brain", "intended"])["uri"] == "qbrain://default/", "default context root changed")
            require(obj(["context", "list", "--uri", "", "--brain", "intended"])["uri"] == "qbrain://default/", "empty URI root changed")
        case("omitted and empty supported defaults remain compatible", defaults)

        if baseline:
            normal = [
                ["memory", "read", "--brain", "intended", "--source", "alpha"],
                ["memory", "read", "--brain", "intended", "--source", "alpha", "--query", "literal", "--limit", "1"],
                ["memory", "read", "--brain", "intended", "--source", "alpha", "--query", ""],
                ["memory", "status", "--brain", "intended", "--source", "alpha", "--event", events["intended", "alpha"]],
                ["context", "list", "--brain", "intended", "--source", "alpha"],
                ["context", "read", "--brain", "intended", "--source", "alpha", "--uri", "qbrain://alpha/resources/docs/", "--layer", "L1"],
                ["context", "read", "--brain", "intended", "--source", "alpha", "--uri", "qbrain://alpha/resources/docs/first", "--layer", "L2"],
            ]
            for argv in normal:
                def compatible(argv=argv) -> None:
                    before = snapshot()
                    fixed = run(argv)
                    old = run(argv, executable=baseline)
                    require((fixed.returncode, fixed.stdout, fixed.stderr) == (old.returncode, old.stdout, old.stderr), "baseline byte mismatch")
                    require(before == snapshot(), "compatibility read mutated state")
                case("baseline exact bytes " + repr(argv), compatible)

        def manual_consent() -> None:
            config("intended", "memory.writeback", "off")
            try:
                before = snapshot()
                value = obj(["memory", "capture", "--source", "--manual", "--brain", "intended"], payload("implicit-manual"))
                require(value.get("status") == "skipped" and value.get("archived") is False, "source value granted manual consent")
                require(snapshot() == before, "denied automatic capture wrote application data")
                actual = obj(["memory", "capture", "--source", "--manual", "--manual", "--brain", "intended"], payload("explicit-manual"))
                require(actual["status"] == "archived", "actual manual flag stopped working")
            finally:
                config("intended", "memory.writeback", "salient")
        case("literal --manual cannot grant capture consent; actual flag still works", manual_consent)

        def mutations() -> None:
            source = "--brain"
            cap = obj(["memory", "capture", "--source", source, "--brain", "intended"], payload("mutations"))
            event = cap["event_id"]
            extracted = obj(["memory", "extract", "--source", source, "--event", event, "--method", "local", "--brain", "intended"])
            require(extracted["item_count"] == 1, "extract no longer reaches real event")
            status = obj(["memory", "status", "--source", source, "--event", event, "--brain", "intended"])
            require(status["event_id"] == event, "status event routing changed")
            obj(["memory", "forget", "--source", source, "--event", event, "--brain", "intended"])
            require(all(row["event_id"] != event for row in memory(["read"], source=source)["items"]), "forget did not remove recall")
            pending = obj(["memory", "capture", "--source", source, "--brain", "intended"], payload("drain"))
            drained = obj(["memory", "drain", "--source", source, "--method", "local", "--brain", "intended"])
            require(any(row["event_id"] == pending["event_id"] for row in drained["events"]), "drain used wrong source/brain")
            summary = obj(["context", "summary", "--source", source, "--uri", "qbrain://--brain/resources/docs/", "--method", "extractive", "--brain", "intended"])
            require(summary["status"] == "cached" and summary["provider_calls"] == 0, "summary changed local semantics")
            before = snapshot()
            denied = obj(["context", "summary", "--source", source, "--uri", "qbrain://--brain/resources/docs/", "--method", "model", "--brain", "intended"], expected=1)
            require(denied["error"]["code"] == "external_summary_denied", "provider consent bypass")
            require(before == snapshot(), "denied model summary wrote data")
        case("option-shaped source preserves all memory actions and summary consent", mutations)

        def event_and_method_values() -> None:
            for source in ("--event", "--method"):
                event = events["intended", source]
                status = obj(["memory", "status", "--source", source, "--event", event, "--brain", "intended"])
                require(status["event_id"] == event, "source value shadowed actual event option")
                extracted = obj(["memory", "extract", "--source", source, "--event", event, "--method", "local", "--brain", "intended"])
                require(extracted["event_id"] == event, "source value shadowed actual extraction method")
        case("option-shaped sources cannot shadow event or method values", event_and_method_values)
        case("no accidental brain directories", lambda: require(
            {entry.name for entry in (data / "brains").iterdir()} == set(brains), "unexpected brains: " + repr(sorted(entry.name for entry in (data / "brains").iterdir()))))

    failed = sum(not check["passed"] for check in checks)
    report = {"schema": "qbrain-n47m-process-v1", "source_commit": args.source_commit,
              "platform": platform.platform(), "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
              "baseline_sha256": hashlib.sha256(baseline.read_bytes()).hexdigest() if baseline else None,
              "checks": checks, "command_count": len(commands), "commands": commands,
              "passed": len(checks) - failed, "failed": failed,
              "limits": ["synthetic SQLite only", "no real client or PostgreSQL acceptance", "not an independent subagent review"]}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"N47M: {len(checks)-failed}/{len(checks)} checks passed; {len(commands)} real commands; failures={failed}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
