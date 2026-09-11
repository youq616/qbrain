"""Exercise the real executable and stdio MCP against a disposable SQLite brain.

Python is a CI/test dependency only. No credentials, real databases or model
services are used. Fixtures are written through SQLite after real migrations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile


def run(binary: Path, args: list[str], env: dict[str, str], cwd: Path,
        data: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    proc = subprocess.run([str(binary), *args], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=env, cwd=cwd, timeout=30)
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace"))
    return proc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    binary = parser.parse_args().binary.resolve(strict=True)
    checks = 0

    def check(value: bool, label: str) -> None:
        nonlocal checks
        if not value:
            raise AssertionError(label)
        checks += 1
        print(f"PASS {checks}: {label}", flush=True)

    with tempfile.TemporaryDirectory(prefix="qbrain-n42-mcp-") as tmp:
        root = Path(tmp)
        env = {k: v for k, v in os.environ.items()
               if not k.upper().startswith(("QBRAIN", "OPENAI", "ANTHROPIC"))}
        env.update(HOME=str(root), LOCALAPPDATA=str(root), USERPROFILE=str(root))
        run(binary, ["init", "--brain", "n42-ci"], env, root)
        data_root = root if os.name == "nt" else root / ".local" / "share"
        db_path = data_root / "Qbrain" / "brains" / "n42-ci" / "brain.db"
        check(db_path.is_file(), "real executable creates isolated migrated database")
        with sqlite3.connect(db_path) as db:
            for source in ("alpha", "beta"):
                db.execute("INSERT INTO sources(id,name) VALUES(?,?)", (source, source))
            db.execute("INSERT INTO config(key,value) VALUES('mcp.allowed_sources','alpha')")
            ids = {}
            for source in ("default", "alpha", "beta"):
                body = f"{source.upper()}_ONLY deployment notes 中文😀 " + "中" * 80
                cur = db.execute("INSERT INTO pages(source_id,slug,title,body) VALUES(?,?,?,?)",
                                 (source, "deployment", source.upper() + " deployment", body))
                ids[source] = cur.lastrowid
                db.execute("INSERT INTO facts(page_id,entity_slug,predicate,object_text) VALUES(?,?,?,?)",
                           (cur.lastrowid, "shared-entity", "uses", source.upper() + "_FACT"))
            cur = db.execute("INSERT INTO pages(source_id,slug,title,body,deleted_at) VALUES(?,?,?,?,?)",
                             ("alpha", "deleted", "deleted", "DELETED_ONLY", "2020-01-01 00:00:00"))
            db.execute("INSERT INTO facts(page_id,entity_slug,predicate,object_text) VALUES(?,?,?,?)",
                       (cur.lastrowid, "shared-entity", "uses", "DELETED_FACT"))
            db.execute("INSERT INTO facts(entity_slug,predicate,object_text) VALUES(?,?,?)",
                       ("shared-entity", "uses", "UNOWNED_FACT"))
            db.commit()

        tables = ("pages", "facts", "file_index", "content_chunks", "jobs", "page_versions")

        def snapshot() -> str:
            with sqlite3.connect(db_path) as conn:
                state = {t: conn.execute(f'SELECT * FROM "{t}" ORDER BY rowid').fetchall() for t in tables}
            return hashlib.sha256(repr(state).encode("utf-8")).hexdigest()

        before = snapshot()
        calls = [
            ("get_page", {"slug": "deployment"}),
            ("get_page", {"slug": "deployment", "source_id": "alpha"}),
            ("get_page", {"slug": "deployment", "source_id": "beta"}),
            ("list_pages", {"source_id": "alpha"}),
            ("search", {"query": "deployment", "source_id": "alpha", "no_vector": True, "mode": "conservative"}),
            ("search", {"query": "deployment", "source_id": "beta", "no_vector": True}),
            ("list_facts", {"entity": "shared-entity", "source_id": "alpha"}),
            ("find_trajectory", {"entity": "shared-entity", "source_id": "alpha"}),
            ("think", {"question": "deployment", "source_id": "alpha", "save": True}),
            ("search_by_image", {"path": str(root / "never-read.png")}),
            ("think", {"question": "deployment", "source_id": "alpha"}),
            ("list_pages", {}),
            ("list_facts", {"entity": "shared-entity", "source_id": "beta"}),
        ]
        messages = [{"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
                    {"jsonrpc": "2.0", "method": "notifications/initialized"}]
        messages += [{"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": args}}
                     for i, (name, args) in enumerate(calls, 1)]
        wire = ("\n".join(json.dumps(m, ensure_ascii=False) for m in messages) + "\n").encode("utf-8")
        proc = run(binary, ["serve", "--brain", "n42-ci"], env, root, wire)
        rows = [json.loads(line) for line in proc.stdout.decode("utf-8").splitlines()]
        check(len(rows) == len(calls) + 1, "stdout is NDJSON; no response to initialized notification")
        replies = {r["id"]: r["result"] for r in rows}

        def text(i: int) -> str:
            return "\n".join(c["text"] for c in replies[i]["content"])

        def ok(i: int) -> bool:
            return not replies[i].get("isError", False)

        def structured(i: int):
            return json.loads(replies[i]["content"][-1]["text"])

        check(ok(1) and "DEFAULT_ONLY" in text(1) and "ALPHA_ONLY" not in text(1), "default source remains explicit")
        check(ok(2) and "ALPHA_ONLY" in text(2) and "DEFAULT_ONLY" not in text(2), "same slug loads correct source body")
        check("中文😀" in text(2), "Chinese and emoji survive real MCP UTF-8 round trip")
        check(not ok(3) and "source_not_allowed" in text(3), "unauthorized page read fails closed")
        check(ok(4) and len(structured(4)) == 1 and structured(4)[0]["source_id"] == "alpha", "page listing is source-scoped and excludes deleted pages")
        hits = structured(5)
        check(ok(5) and len(hits) == 1 and hits[0]["source_id"] == "alpha" and hits[0]["page_id"] == ids["alpha"], "search preserves actual source and page ID")
        check(not ok(6) and "source_not_allowed" in text(6), "unauthorized search denied before provider access")
        for i in (7, 8):
            check(ok(i) and "ALPHA_FACT" in text(i) and all(x not in text(i) for x in ("BETA_FACT", "DEFAULT_FACT", "DELETED_FACT", "UNOWNED_FACT")), f"{calls[i - 1][0]} excludes cross-source, deleted and unowned facts")
        check(not ok(9) and "write_denied" in text(9), "read-only synthesis rejects save before model call")
        check(not ok(10), "MCP image query refuses local filesystem access")
        check(ok(11) and structured(11).get("degraded") is True and "ALPHA_ONLY" in text(11) and all(x not in text(11) for x in ("BETA_ONLY", "DEFAULT_ONLY")), "real synthesis evidence uses matched source; keyless mode is explicit")
        check(ok(12) and len(structured(12)) == 1 and structured(12)[0]["source_id"] == "default", "unscoped MCP listing does not list all sources")
        check(not ok(13), "unauthorized fact read denied")
        check(snapshot() == before, "read and denied calls do not change page/fact/file/chunk/job/version rows")
        print(f"MCP production integration: {checks} checks passed; no live model API or user data used.")


if __name__ == "__main__":
    main()
