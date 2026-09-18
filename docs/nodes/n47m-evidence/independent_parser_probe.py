"""Separate N47M engineering self-review probe; does not import product tests.

Use only temporary synthetic SQLite brains. Optional baseline comparisons use
ordinary reads on the same state and known-negative inputs on a separate copy.
This is a coordinator self-review tool, not a separate agent or certification.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import tempfile


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binary", type=Path, required=True)
    ap.add_argument("--baseline", type=Path)
    ap.add_argument("--report", type=Path, required=True)
    ns = ap.parse_args()
    binary = ns.binary.resolve(strict=True)
    baseline = ns.baseline.resolve(strict=True) if ns.baseline else None
    groups, failures, negatives, trace = {}, [], [], []

    def check(group, ok, description):
        count = groups.setdefault(group, {"cases": 0, "failed": 0})
        count["cases"] += 1
        if not ok:
            count["failed"] += 1
            failures.append({"group": group, "description": description})

    with tempfile.TemporaryDirectory(prefix="qbrain-n47m-review-") as temp:
        root = Path(temp) / "中文 audit 😀"
        root.mkdir()
        env = {k: v for k, v in os.environ.items()
               if not k.upper().startswith(("QBRAIN", "OPENAI", "ANTHROPIC"))}
        env.update(HOME=str(root), USERPROFILE=str(root), LOCALAPPDATA=str(root))

        def data_dir(where=root):
            return (where if os.name == "nt" else where / ".local/share") / "Qbrain"

        def sql(brain, query, values=(), where=root):
            with closing(sqlite3.connect(data_dir(where) / "brains" / brain / "brain.db")) as db:
                result = db.execute(query, values).fetchall()
                db.commit()
                return result

        def config(brain, key, value, where=root):
            sql(brain, "INSERT INTO config(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value), where)

        def state(where=root):
            result = {}
            for dbfile in sorted((data_dir(where) / "brains").glob("*/brain.db")):
                with closing(sqlite3.connect(dbfile)) as db:
                    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                    result[dbfile.parent.name] = {t: sorted(db.execute('SELECT * FROM "' + t.replace('"', '""') + '"').fetchall(), key=repr) for t in tables}
            return hashlib.sha256(repr(result).encode()).hexdigest()

        def run(argv, payload=None, *, executable=binary, where=root, extra=None):
            raw = encode(payload) if payload is not None else b""
            current = {**env, "HOME": str(where), "USERPROFILE": str(where), "LOCALAPPDATA": str(where), **(extra or {})}
            p = subprocess.run([str(executable), *argv], input=raw, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=current, cwd=where, timeout=20)
            trace.append({"binary": "baseline" if executable == baseline else "candidate", "argv": argv,
                          "stdin_sha256": hashlib.sha256(raw).hexdigest(), "exit": p.returncode,
                          "stdout_sha256": hashlib.sha256(p.stdout).hexdigest(),
                          "stderr_sha256": hashlib.sha256(p.stderr).hexdigest()})
            return p

        def value(p):
            try:
                return json.loads(p.stdout)
            except (ValueError, UnicodeError):
                return {}

        def flatten(options):
            return [part for pair in options for part in pair]

        def packet(fragment, content):
            return {"session_id": "review-session", "fragment_id": fragment,
                    "messages": [{"role": "user", "content": content}]}

        brain_names = ("intended", "environment", "configured", "default", "--manual")
        literal_sources = ("alpha", "--brain", "--source", "--manual", "--uri", "--layer", "--offset", "--revision", "--limit", "--max-bytes", "--event", "--method")
        quotes, bodies, events = {}, {}, {}
        for brain in brain_names:
            p = run(["init", "--brain", brain, "--no-default"])
            if p.returncode:
                raise RuntimeError("fixture init failed: " + (p.stdout + p.stderr).decode(errors="replace"))
            config(brain, "memory.writeback", "salient")
            for source in literal_sources if brain == "intended" else ("alpha", "--brain"):
                sql(brain, "INSERT INTO sources(id,name) VALUES(?,?)", (source, source))
                quote = f"I prefer exact {brain}/{source} --brain --source --limit --max-bytes --manual --query 中文😀."
                body = f"RAW {brain}/{source}\r\n中文😀 exact source page."
                quotes[brain, source], bodies[brain, source] = quote, body
                # Safe controls work on both parsers: real keys precede option-shaped source values.
                p = run(["memory", "capture", "--brain", brain, "--manual", "--source", source], packet(source, quote))
                event = value(p).get("event_id")
                if p.returncode or not event:
                    raise RuntimeError("fixture capture failed")
                events[brain, source] = event
                p = run(["memory", "extract", "--brain", brain, "--event", event, "--method", "local", "--source", source])
                if p.returncode or value(p).get("item_count") != 1:
                    raise RuntimeError("fixture extraction failed")
                sql(brain, "INSERT INTO pages(source_id,slug,title,body) VALUES(?,?,?,?)", (source, "docs/first", "Review page", body))

        def memory_ok(p, brain="intended", source="alpha"):
            obj = value(p)
            items = obj.get("items", [])
            return (p.returncode == 0 and obj.get("source_id") == source and len(items) == 1
                    and items[0].get("quote") == quotes[brain, source]
                    and items[0].get("event_id") == events[brain, source])

        def context_ok(p, brain="intended", source="alpha"):
            obj = value(p)
            return (p.returncode == 0 and obj.get("source_id") == source
                    and obj.get("content") == bodies[brain, source]
                    and obj.get("revision") == hashlib.sha256(bodies[brain, source].encode()).hexdigest()
                    and obj.get("layer") == "L2" and obj.get("provider_calls") == 0)

        before = state()
        for needle in ("--brain", "--source", "--limit", "--max-bytes", "--manual", "--query"):
            options = [("--brain", "intended"), ("--source", "alpha"), ("--query", needle), ("--limit", "5"), ("--max-bytes", "8192")]
            for order in itertools.permutations(options):
                argv = ["memory", "read", *flatten(order)]
                check("memory_all_5_option_permutations", memory_ok(run(argv)), repr(argv))
        for source in literal_sources:
            options = [("--brain", "intended"), ("--source", source), ("--uri", f"qbrain://{source}/resources/docs/first"), ("--layer", "L2")]
            for order in itertools.permutations(options):
                argv = ["context", "read", *flatten(order)]
                check("context_all_4_option_permutations", context_ok(run(argv), source=source), repr(argv))
        check("read_side_effects", before == state(), "all permutation reads preserve application rows in every fixture brain")
        check("read_side_effects", {p.name for p in (data_dir()/"brains").iterdir()} == set(brain_names), "no accidental brain directories")

        for file_brain, extra, actual, explicit in (
            (None, {}, "default", []),
            ("configured", {}, "configured", []),
            ("configured", {"QBRAIN_BRAIN": ""}, "configured", []),
            ("configured", {"QBRAIN_BRAIN": "environment"}, "environment", []),
            ("configured", {"QBRAIN_BRAIN": "environment"}, "intended", ["--brain", "intended"]),
        ):
            path = data_dir()/"config.json"
            if file_brain is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(encode({"brain_id": file_brain}))
            p = run(["memory", "read", "--query", "--brain", "--source", "alpha", *explicit], extra=extra)
            check("brain_precedence", memory_ok(p, actual), repr((file_brain, extra, explicit)))
            p = run(["context", "read", "--source", "--brain", "--uri", "qbrain://--brain/resources/docs/first", "--layer", "L2", *explicit], extra=extra)
            check("brain_precedence", context_ok(p, actual, "--brain"), repr((file_brain, extra, explicit)))
        (data_dir()/"config.json").write_bytes(encode({"brain_id": "intended"}))

        before = state()
        invalid = []
        for action in ("capture", "extract", "status", "forget", "drain", "read"):
            invalid += [(["memory", action, "--brain", "stray", "--bogus", "x"], 2, "invalid_cli_argument"),
                        (["memory", action, "--brain", "stray", "--source"], 2, "invalid_cli_argument"),
                        (["memory", action, "--brain", "stray", "--source", "alpha", "--source", "beta"], 2, "duplicate_argument")]
        for action in ("read", "list", "summary"):
            invalid += [(["context", action, "--brain", "stray", "--bogus", "x"], 1, "invalid_cli_argument"),
                        (["context", action, "--brain", "stray", "--source"], 1, "invalid_cli_argument"),
                        (["context", action, "--brain", "stray", "--source", "alpha", "--source", "beta"], 1, "invalid_cli_argument")]
        for argv, exit_code, code in invalid:
            p = run(argv)
            check("invalid_preopen", p.returncode == exit_code and code.encode() in p.stdout+p.stderr, repr(argv))
        check("invalid_preopen", before == state() and not (data_dir()/"brains/stray").exists(), "rejected syntax opens no stray brain or mutates rows")

        for brain, source in (("intended", "--manual"), ("--manual", "alpha")):
            config(brain, "memory.writeback", "off")
            for order in itertools.permutations([("--brain", brain), ("--source", source)]):
                before = state()
                p = run(["memory", "capture", *flatten(order)], packet("automatic-"+brain+source, "I prefer explicit consent."))
                check("manual_consent", p.returncode == 0 and value(p).get("status") == "skipped" and value(p).get("archived") is False and before == state(), repr(order))
            p = run(["memory", "capture", "--source", source, "--manual", "--brain", brain], packet("manual-"+brain+source, "I prefer explicit consent."))
            check("manual_consent", p.returncode == 0 and value(p).get("status") == "archived", "real --manual works for "+brain+"/"+source)

        if baseline:
            normal = [
                ["memory", "read", "--brain", "intended", "--source", "alpha"],
                ["memory", "read", "--brain", "intended", "--source", "alpha", "--query", "exact"],
                ["memory", "read", "--brain", "intended", "--source", "alpha", "--query", ""],
                ["memory", "read", "--brain", "intended", "--source", "alpha", "--limit", ""],
                ["memory", "status", "--brain", "intended", "--event", events["intended", "alpha"], "--source", "alpha"],
                ["context", "list", "--brain", "intended", "--source", "alpha"],
                ["context", "read", "--brain", "intended", "--source", "alpha", "--uri", "qbrain://alpha/resources/docs/first", "--layer", "L2"],
                ["context", "read", "--brain", "intended", "--source", "alpha", "--uri", "qbrain://alpha/resources/docs/", "--layer", "L1"],
                *[item[0] for item in invalid],
            ]
            before = state()
            for argv in normal:
                new, old = run(argv), run(argv, executable=baseline)
                check("baseline_exact_bytes", (new.returncode, new.stdout, new.stderr) == (old.returncode, old.stdout, old.stderr), repr(argv))
            check("baseline_exact_bytes", before == state(), "ordinary baseline comparison preserves all fixture rows")
            negative_root = Path(temp)/"baseline-negative"
            shutil.copytree(root, negative_root)
            for label, argv, is_correct in (
                ("source_shadowing", ["memory", "read", "--brain", "intended", "--query", "--source", "--limit", "5", "--source", "alpha"], memory_ok),
                ("brain_shadowing", ["memory", "read", "--query", "--brain", "--source", "alpha", "--brain", "intended"], memory_ok),
                ("context_brain_shadowing", ["context", "read", "--source", "--brain", "--uri", "qbrain://--brain/resources/docs/first", "--layer", "L2", "--brain", "intended"], lambda p: context_ok(p, source="--brain")),
            ):
                new = run(argv)
                old = run(argv, executable=baseline, where=negative_root)
                check("baseline_known_defects", is_correct(new) and not is_correct(old), label)
                negatives.append({"name": label, "argv": argv, "candidate_exit": new.returncode, "baseline_exit": old.returncode,
                                  "baseline_stdout": old.stdout.decode(errors="replace"), "baseline_stderr": old.stderr.decode(errors="replace")})
            argv = ["memory", "capture", "--source", "--manual", "--brain", "intended"]
            raw = packet("negative-manual", "I prefer explicit consent.")
            new = run(argv, raw)
            old = run(argv, raw, executable=baseline, where=negative_root)
            check("baseline_known_defects", value(new).get("status") == "skipped" and value(old).get("status") == "archived", "source value cannot authorize manual capture")
            negatives.append({"name": "manual_consent", "argv": argv, "candidate_status": value(new).get("status"), "baseline_status": value(old).get("status")})

    report = {"schema": "qbrain-n47m-independent-probe-v1", "reviewer": "coordinating ChatGPT; separate engineering self-review, not another agent",
              "platform": platform.platform(), "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
              "baseline_sha256": hashlib.sha256(baseline.read_bytes()).hexdigest() if baseline else None,
              "groups": groups, "cases": sum(x["cases"] for x in groups.values()), "failed": len(failures),
              "failures": failures, "baseline_counterexamples": negatives, "command_count": len(trace),
              "command_trace_sha256": hashlib.sha256(encode(trace)).hexdigest(),
              "limits": ["temporary synthetic SQLite", "no real client/PG/provider", "no universal correctness claim"]}
    ns.report.parent.mkdir(parents=True, exist_ok=True)
    ns.report.write_bytes(encode(report)+b"\n")
    ns.report.with_suffix(".trace.json").write_bytes(encode(trace)+b"\n")
    print(json.dumps({k: report[k] for k in ("cases", "failed", "command_count", "groups")}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
