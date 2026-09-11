"""Production CLI/MCP context and maintenance tests plus a bounded fixture benchmark.

All databases, configuration and text are synthetic. The benchmark measures bytes
and end-to-end local process latency, not model quality, provider tokens or money.
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
import statistics
import subprocess
import tempfile
import time


def wire(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--binary", type=Path, required=True)
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    binary = args.binary.resolve(strict=True)
    checks = 0

    def check(ok: bool, label: str):
        nonlocal checks
        if not ok:
            raise AssertionError(label)
        checks += 1
        print(f"PASS {checks}: {label}", flush=True)

    with tempfile.TemporaryDirectory(prefix="qbrain-context-process-") as tmp:
        root = Path(tmp) / "中文 source 😀"; root.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("QBRAIN", "OPENAI", "ANTHROPIC"))}
        env.update(HOME=str(root), LOCALAPPDATA=str(root), USERPROFILE=str(root))
        data_root = root if os.name == "nt" else root / ".local/share"
        dbpath = data_root / "Qbrain/brains/context-ci/brain.db"

        def run(arguments: list[str], data: bytes = b"", ok: bool = True):
            proc = subprocess.run([str(binary), *arguments, "--brain", "context-ci"], input=data,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=env, cwd=root, timeout=30)
            if (proc.returncode == 0) != ok:
                raise AssertionError(f"exit={proc.returncode}: {arguments}: {(proc.stdout+proc.stderr).decode('utf-8',errors='replace')}")
            return proc

        def context(action: str, *options: str, ok: bool = True):
            proc = run(["context", action, "--source", "alpha", *options], ok=ok)
            return json.loads(proc.stdout.decode("utf-8"))

        def sql(query: str, parameters: tuple = ()):
            with closing(sqlite3.connect(dbpath)) as db:
                rows = db.execute(query, parameters).fetchall(); db.commit(); return rows

        def snapshot():
            with closing(sqlite3.connect(dbpath)) as db:
                names = [v[0] for v in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                return hashlib.sha256(repr({n: db.execute('SELECT * FROM "'+n+'"').fetchall() for n in names}).encode()).hexdigest()

        run(["init", "--no-default"])
        check(dbpath.is_file(), "real executable creates isolated context test brain")
        check(not (data_root / "Qbrain/config.json").exists(), "--no-default does not create a global brain selection")
        sql("INSERT INTO sources(id,name) VALUES('alpha','alpha'),('beta','beta')")
        original = ("中文😀 source evidence with a literal \\\"quoted\\\" value\r\n" * 1000)
        for source, body in (("alpha", original), ("beta", "PRIVATE_BETA_ONLY")):
            sql("INSERT INTO pages(source_id,slug,title,body) VALUES(?,?,?,?)", (source, "docs/first", "Original Chinese notes", body))
        before = snapshot()
        root_card = context("list")
        check(len(root_card["entries"]) == 3, "logical namespace root exposes exactly three namespaces")
        uri = "qbrain://alpha/resources/docs/"
        card = context("read", "--uri", uri, "--layer", "L1", "--max-bytes", "2048")
        check(card["method"] == "extractive" and card["provider_calls"] == 0, "uncached directory is explicitly extractive without a model")
        check(len(wire(card)) <= 2048 and "PRIVATE_BETA_ONLY" not in str(card), "directory output is bounded and source scoped")
        check(before == snapshot(), "uncached read initializes no tables and writes no application state")
        summary = context("summary", "--uri", uri)
        check(summary["method"] == "extractive", "explicit summary persists the current directory signature")
        check(len(list(dbpath.parent.glob("brain.db.pre-context-v1-*.bak"))) == 1, "first context initialization creates an actual backup")
        check(len(sql("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'ctx_page_%'")) == 3, "production schema installs three invalidation triggers")
        before = snapshot()
        check(context("read", "--uri", uri)["cache_status"] == "fresh", "restarted process reads the cached directory")
        check(snapshot() == before, "fresh read does not update cache bookkeeping or usage")
        chunks = []; revision = None; offset = 0
        for _ in range(500):
            options = ["--uri", uri+"first", "--layer", "L2", "--max-bytes", "4096"]
            if offset:
                options.extend(["--offset", str(offset), "--revision", revision])
            page = context("read", *options)
            check(len(wire(page)) <= 4096, "raw page respects serialized byte budget")
            chunks.append(page["content"]); revision = page["revision"]
            if page["next_offset"] is None:
                break
            check(page["next_offset"] > offset, "raw page offset advances on a UTF-8 boundary")
            offset = page["next_offset"]
        else:
            raise AssertionError("raw pagination did not terminate")
        check("".join(chunks).encode() == original.encode(), "raw Chinese/emoji/CRLF content reconstructs byte-identically")
        sql("UPDATE pages SET body='EDITED_ALPHA_ONLY' WHERE source_id='alpha' AND slug='docs/first'")
        dirty = sql("SELECT dirty,l0,l1,refs_json FROM context_cache WHERE source_id='alpha'")[0]
        check(dirty == (1, "", "", "[]"), "editing raw evidence clears obsolete derived cache text")
        stale = context("read", "--uri", uri, "--layer", "L1")
        check(stale["cache_status"] == "stale" and "EDITED_ALPHA_ONLY" in stale["content"], "stale cache falls back to current evidence only")
        context("read", "--uri", uri+"first", "--layer", "L2", "--offset", "1", "--revision", revision, ok=False)
        check(True, "continuation with obsolete revision is rejected")
        before = snapshot()
        context("summary", "--uri", uri, "--method", "model", ok=False)
        check(snapshot() == before, "model summary without consent makes no writes or provider call")
        sql("INSERT INTO config(key,value) VALUES('context.external_summary','allow')")
        missing = context("summary", "--uri", uri, "--method", "model")
        check(missing["status"] == "unconfigured" and missing["provider_calls"] == 0, "missing model credentials are not faked as successful extraction")
        sql("INSERT INTO config(key,value) VALUES('mcp.allowed_sources','alpha')")

        def mcp(messages: list[dict], profile: str):
            return [json.loads(line) for line in run(["serve", "--tool-profile", profile], b"\n".join(wire(x) for x in messages)+b"\n").stdout.decode("utf-8").splitlines()]

        listing = {"jsonrpc":"2.0","id":1,"method":"tools/list"}
        full = mcp([listing], "full")[0]["result"]
        compact = mcp([listing], "memory")[0]["result"]
        names = {t["name"] for t in compact["tools"]}
        check(names == {"memory_read","memory_write","context_read","context_write","search","get_page"}, "actual compact MCP process exposes exactly six tools")
        check(len(full["tools"]) == 112, "full profile preserves original tools plus explicit additions")
        check(len(wire(compact)) < len(wire(full)), "compact profile reduces actual tool-definition bytes")
        def call(i, name, arguments):
            return {"jsonrpc":"2.0","id":i,"method":"tools/call","params":{"name":name,"arguments":arguments}}
        before = snapshot()
        replies = mcp([call(1,"context_read",{"source_id":"beta","uri":"qbrain://beta/resources/docs/"}),
                       call(2,"context_read",{"source_id":"alpha","uri":uri}),
                       call(3,"context_write",{"source_id":"alpha","uri":uri}),
                       call(4,"list_pages",{"source_id":"alpha"})], "memory")
        check("source_not_allowed" in json.dumps(replies[0]), "source policy is enforced in compact profile")
        check(not replies[1]["result"].get("isError",False), "authorized context is available through the real MCP transport")
        check(replies[2]["result"].get("isError",False), "compact read-only process rejects summary writes")
        check("not available" in json.dumps(replies[3]).lower() or "not found" in json.dumps(replies[3]).lower(), "hidden full-profile tool cannot be called by guessing its name")
        check(before == snapshot(), "MCP reads and refused calls leave all application tables unchanged")
        # Deferred automatic capture is drained through an explicit operator command.
        run(["config","set","memory.writeback","salient"])
        payload = {"session_id":"deferred","fragment_id":"first","messages":[{"role":"user","content":"I prefer bounded local maintenance."}]}
        event = json.loads(run(["memory","capture","--source","alpha"], wire(payload)).stdout)
        check(event["status"] == "archived", "deferred capture is not labelled extracted")
        drained = json.loads(run(["memory","drain","--source","alpha"]).stdout)
        check(len(drained["events"]) == 1 and drained["events"][0]["item_count"] == 1, "maintenance command processes an actual pending event")
        check(json.loads(run(["memory","drain","--source","alpha"]).stdout)["status"] == "empty", "maintenance retries do not duplicate already classified events")
        denied = json.loads(run(["memory","drain","--source","alpha","--method","model"]).stdout)
        check(denied["reason"] == "external_extraction_denied", "batch maintenance never grants its own external consent")
        # Deterministic retrieval fixture; no model, no factual-quality comparison.
        full_bytes = 0
        for i in range(96):
            body = (f"Reference {i:03d}: documented operating requirement. 中文\n" * 160)
            full_bytes += len(body.encode())
            sql("INSERT INTO pages(source_id,slug,title,body) VALUES(?,?,?,?)", ("alpha",f"benchmark/doc-{i:03d}",f"Document {i:03d}",body))
        bench_uri = "qbrain://alpha/resources/benchmark/"
        context("summary", "--uri", bench_uri)
        times=[];last=None
        for _ in range(9):
            start=time.perf_counter_ns();last=context("read","--uri",bench_uri,"--layer","L1");times.append((time.perf_counter_ns()-start)/1e6)
        check(last["cache_status"] == "fresh" and last["page_count"] == 96, "benchmark uses a fresh 96-document production cache")
        report = {"format_version":1,"scope":"synthetic local fixture; no LLM answer-quality or billing evaluation",
                  "platform":platform.platform(),"checks":checks,"documents":96,
                  "original_body_bytes":full_bytes,"cached_L1_response_bytes":len(wire(last)),
                  "cached_L1_truncated":last["truncated"],"full_tool_count":len(full["tools"]),"compact_tool_count":len(compact["tools"]),
                  "full_tool_definition_bytes":len(wire(full)),"compact_tool_definition_bytes":len(wire(compact)),
                  "cached_read_with_process_start_median_ms":statistics.median(times),"cached_read_with_process_start_max_ms":max(times),
                  "latency_samples":len(times),"provider_calls":0,"provider_tokens":None,"monetary_savings":None,
                  "accuracy_improvement":None,"limitations":["L1 is an extractive preview, not all original evidence", "Byte reduction is not token or fee reduction", "Latency includes process start and storage open", "No cross-hardware latency guarantee"]}
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")
        print(json.dumps(report,ensure_ascii=False),flush=True)
        print(f"N45/N46 production process checks: {checks} passed; no live model or real user data.")


if __name__ == "__main__":
    main()
