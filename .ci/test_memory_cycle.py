"""N43/N44A real-process checks. Synthetic isolated data; no live provider.

Python is a test dependency, never a product/Agent runtime dependency.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import time


def encode(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    original = parser.parse_args().binary.resolve(strict=True)
    checks = 0
    retries = 0

    def check(value: bool, label: str) -> None:
        nonlocal checks
        if not value:
            raise AssertionError(label)
        checks += 1
        print(f"PASS {checks}: {label}", flush=True)

    with tempfile.TemporaryDirectory(prefix="qbrain-n43-") as tmp:
        root = Path(tmp) / "中文 space 😀"
        root.mkdir()
        binary = root / ("qbrain.exe" if os.name == "nt" else "qbrain")
        shutil.copy2(original, binary)
        env = {k: v for k, v in os.environ.items()
               if not k.upper().startswith(("QBRAIN", "OPENAI", "ANTHROPIC"))}
        env.update(HOME=str(root), LOCALAPPDATA=str(root), USERPROFILE=str(root))
        data_root = root if os.name == "nt" else root / ".local" / "share"
        db_path = data_root / "Qbrain" / "brains" / "memory-ci" / "brain.db"

        def process(args: list[str], raw: bytes = b"", *, expected: int | None = 0,
                    extra: dict[str, str] | None = None, retry_busy: bool = False):
            nonlocal retries
            for attempt in range(12 if retry_busy else 1):
                p = subprocess.run([str(binary), *args, "--brain", "memory-ci"], input=raw,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   cwd=root, env={**env, **(extra or {})}, timeout=30)
                diagnostic = (p.stdout + p.stderr).decode("utf-8", errors="replace")
                if (retry_busy and p.returncode and attempt < 11 and
                        ("locked" in diagnostic or "busy" in diagnostic or "memory_storage_error" in diagnostic)):
                    retries += 1
                    time.sleep(0.02 * (attempt + 1))
                    continue
                if expected is not None and (p.returncode == 0) != (expected == 0):
                    raise AssertionError(f"Unexpected exit {p.returncode} for {args}: {diagnostic}")
                return p
            raise AssertionError("unreachable retry state")

        def cli(action: str, opts: list[str] | None = None, payload: object = None,
                source: str = "alpha", **kwargs):
            raw = b"" if payload is None else encode(payload)
            p = process(["memory", action, "--source", source, *(opts or [])], raw, **kwargs)
            return json.loads(p.stdout.decode("utf-8"))

        def sql(query: str, params: tuple = (), *, all_rows: bool = False):
            with closing(sqlite3.connect(db_path, timeout=10)) as db:
                cur = db.execute(query, params)
                rows = cur.fetchall()
                db.commit()
                return rows if all_rows else (rows[0][0] if rows else None)

        def config(key: str, value: str) -> None:
            sql("INSERT INTO config(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

        def count(table: str) -> int:
            return sql(f'SELECT COUNT(*) FROM "{table}"')

        def snapshot() -> str:
            with closing(sqlite3.connect(db_path)) as db:
                tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                contents = {t: db.execute(f'SELECT * FROM "{t}"').fetchall() for t in tables}
            return hashlib.sha256(repr(contents).encode("utf-8")).hexdigest()

        def mcp(calls: list[tuple[str, object]], *, allow_write: bool = False,
                extra: dict[str, str] | None = None):
            messages = [{"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
                        {"jsonrpc": "2.0", "method": "notifications/initialized"}]
            messages += [{"jsonrpc": "2.0", "id": i, "method": "tools/call",
                          "params": {"name": name, "arguments": args}}
                         for i, (name, args) in enumerate(calls, 1)]
            p = process(["serve", *( ["--allow-write"] if allow_write else [])],
                        b"\n".join(encode(m) for m in messages) + b"\n", extra=extra)
            rows = [json.loads(line) for line in p.stdout.decode("utf-8").splitlines()]
            if len(rows) != len(calls) + 1:
                raise AssertionError("MCP NDJSON response count")
            return [r["result"] for r in rows[1:]]

        def content(result: dict):
            return json.loads(result["content"][-1]["text"])

        def payload(fragment: str = "fragment-中文😀", session: str = "session-中文😀", suffix: str = "") -> dict:
            return {"session_id": session, "fragment_id": fragment, "messages": [
                {"role": "user", "content": "我偏好不用 Docker，使用 Windows 11。😀" + suffix},
                {"role": "assistant", "content": "I infer that the user likes risky investments."},
                {"role": "user", "content": "I decided to keep the original evidence.\r\nNo paraphrases."}]}

        process(["init"])
        check(db_path.is_file(), "native process starts and opens data under Chinese/space/emoji path")
        for source in ("alpha", "beta"):
            sql("INSERT INTO sources(id,name) VALUES(?,?)", (source, source))
        config("memory.writeback", "off")
        before = snapshot()
        check(cli("read")["initialized"] is False, "read does not initialize optional module")
        check(cli("capture", payload=payload())["status"] == "skipped", "automatic off does not archive")
        check(snapshot() == before, "off and read do not change database tables or rows")
        config("memory.writeback", "salient")
        cap = cli("capture", payload=payload())
        event_id = cap["event_id"]
        check(cap["status"] == "archived" and cap["extracted"] is False, "capture is explicitly archived, not extracted")
        check(len(list(db_path.parent.glob("brain.db.pre-memory-v1-*.bak"))) >= 1, "optional module initialization creates on-disk backup")
        row = sql("SELECT payload_hash FROM memory_events WHERE event_id=?", (event_id,))
        canonical = encode({"messages": payload()["messages"], "expires_at": 0})
        check(row == hashlib.sha256(canonical).hexdigest(), "portable production SHA-256 equals independent Python reference")
        check(count("memory_events") == 1 and count("memory_items") == 0, "one archive event without invented memory facts")
        check(count("jobs") == 0 and count("content_chunks") == 0, "capture does not start embedding, jobs or chunk indexing")
        check(cli("read")["items"] == [], "unextracted archive is not returned as a memory item")
        check(cli("capture", payload=payload())["duplicate"] is True and count("memory_events") == 1, "process restart/retry is idempotent")
        conflict = cli("capture", payload=payload(suffix="changed"), expected=1)
        check(conflict["error"]["code"] == "fragment_conflict", "changed fragment cannot overwrite previous evidence")
        result = cli("extract", ["--event", event_id])
        check(result["item_count"] == 2 and result["method"] == "explicit-markers-v1", "local extraction labels explicit whole user statements only")
        recalled = cli("read", ["--query", "不用 Docker"])
        check(len(recalled["items"]) == 1 and recalled["items"][0]["quote"] == payload()["messages"][0]["content"], "Unicode argv and reopened process recall preserve exact negated user statement")
        check("risky investments" not in json.dumps(cli("read")), "assistant inference is not promoted to memory")
        small = process(["memory", "read", "--source", "alpha", "--max-bytes", "512"])
        check(len(small.stdout.rstrip(b"\r\n")) <= 512, "serialized recall respects byte budget without chopping quotes")
        check(cli("status", ["--event", event_id])["usage"][0]["input_tokens"] == 0, "local extraction usage is zero, not a paid model estimate")
        check(cli("status", ["--event", event_id])["usage"][0]["cost"] is None, "unpriced monetary cost remains unknown")
        beta_id = cli("capture", payload=payload(suffix="BETA_ONLY"), source="beta")["event_id"]
        cli("extract", ["--event", beta_id], source="beta")
        default_id = cli("capture", payload=payload(suffix="DEFAULT_ONLY"), source="default")["event_id"]
        cli("extract", ["--event", default_id], source="default")
        check("BETA_ONLY" not in json.dumps(cli("read")), "same session and fragment are isolated by source")
        config("mcp.allowed_sources", "alpha")
        before = snapshot()
        replies = mcp([
            ("memory_read", {"source_id": "alpha", "query": "不用 Docker"}),
            ("memory_read", {"source_id": "beta"}),
            ("memory_read", {}),
            ("memory_read", {"source_id": "alpha", "limit": True}),
            ("memory_read", {"source_id": "alpha", "limit": 1.0}),
            ("memory_read", {"source_id": "alpha", "limit": "1"}),
            ("memory_read", {"source_id": "alpha", "unexpected": 1}),
            ("memory_read", {"source_id": "alpha", "event_id": beta_id}),
            ("memory_write", {"source_id": "alpha", "action": "capture", "payload": encode(payload("denied")).decode()}),
        ], extra={"QBRAIN_SOURCE": "beta"})
        check(not replies[0].get("isError", False) and len(content(replies[0])["items"]) == 1, "real MCP returns authorized source memory")
        check(replies[1].get("isError") is True and "source_not_allowed" in str(replies[1]), "real MCP denies forbidden source")
        check(not replies[2].get("isError", False) and content(replies[2])["source_id"] == "default", "MCP default is explicit, not ambient QBRAIN_SOURCE")
        check(all(r.get("isError") is True for r in replies[3:7]), "MCP rejects bool, float, numeric string and extra arguments")
        check(replies[7].get("isError") is True and "event_not_found" in str(replies[7]), "cross-source event identifier gives no event data")
        check(replies[8].get("isError") is True and "write_denied" in str(replies[8]), "MCP memory writes remain default-deny")
        check(snapshot() == before, "MCP reads and denied calls do not mutate application tables")
        before = count("memory_events")
        replies = mcp([
            ("memory_write", {"source_id": "alpha", "action": "capture", "payload": payload("object-coercion")}),
            ("memory_write", {"source_id": "alpha", "action": "capture", "payload": encode(payload("manual-bypass")).decode(), "manual": True}),
            ("memory_write", {"source_id": "beta", "action": "forget", "event_id": beta_id}),
        ], allow_write=True)
        check(all(r.get("isError") is True for r in replies) and count("memory_events") == before, "write opt-in does not allow type coercion, manual-policy bypass or forbidden sources")
        bad = payload("secret")
        bad["messages"][0]["content"] = "api_key=synthetic-not-a-real-key"
        check(cli("capture", payload=bad, expected=1)["error"]["code"] == "sensitive_material_rejected", "obvious credential material rejected before archival")
        before = snapshot()
        process(["memory", "capture", "--source", "alpha"], b"x" * 262145, expected=1)
        process(["memory", "capture", "--source", "alpha"], b"{\xff}", expected=1)
        process(["memory", "read", "--limit", "1oops"], expected=1)
        process(["memory", "read", "--limit", "1", "--limit", "2"], expected=1)
        check(snapshot() == before, "oversize, invalid UTF-8, malformed and duplicate CLI args cause no memory mutation")
        config("memory.writeback", "off")
        manual = cli("capture", ["--manual"], payload("manual"))
        check(manual["status"] == "archived", "explicit local manual archive remains possible with automatic writeback off")
        check(cli("extract", ["--event", event_id], expected=1)["error"]["code"] == "writeback_off", "automatic event extraction respects current off policy")
        config("memory.writeback", "salient")
        model_id = cli("capture", payload=payload("model-unconfigured"))["event_id"]
        check(cli("extract", ["--event", model_id, "--method", "model"], expected=1)["error"]["code"] == "external_extraction_denied", "model extraction requires separate persistent consent")
        config("memory.external_extraction", "allow")
        model = cli("extract", ["--event", model_id, "--method", "model"])
        check(model["reason"] == "model_unconfigured" and cli("status", ["--event", model_id])["attempts"] == 0, "no key means archived without simulated extraction or usage")
        config("memory.external_extraction", "deny")
        concurrent = payload("concurrent")
        with ThreadPoolExecutor(max_workers=6) as pool:
            captures = list(pool.map(lambda _: cli("capture", payload=concurrent, retry_busy=True), range(12)))
        concurrent_id = captures[0]["event_id"]
        check(len({c["event_id"] for c in captures}) == 1 and sum(not c["duplicate"] for c in captures) == 1, "twelve concurrent processes create exactly one event; retries converge")
        check(sql("SELECT count(*) FROM memory_events WHERE event_id=?", (concurrent_id,)) == 1, "unique event constraint holds across real connections")
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: cli("extract", ["--event", concurrent_id], expected=None, retry_busy=True), range(8)))
        check(any(r.get("status") == "extracted" for r in results) and all(r.get("status") == "extracted" or r.get("error", {}).get("code") == "extraction_busy" for r in results), "competing extractors either succeed/idempotently finish or report explicit busy")
        check(sql("SELECT count(*) FROM memory_items WHERE event_id=?", (concurrent_id,)) == 2, "concurrent extractors cannot duplicate published memory")
        sql("UPDATE pages SET deleted_at='2026-01-01 00:00:00' WHERE id=(SELECT page_id FROM memory_events WHERE event_id=?)", (concurrent_id,))
        check(all(r["event_id"] != concurrent_id for r in cli("read")["items"]), "deleted evidence ceases to participate in recall")
        cli("forget", ["--event", concurrent_id])
        check(sql("SELECT count(*) FROM pages WHERE slug=?", ("sessions/" + concurrent_id,)) == 0, "forget removes an unchanged soft-deleted archive")
        check(cli("capture", payload=concurrent)["status"] == "forgotten", "process replay cannot resurrect forgotten memory")
        check(cli("extract", ["--event", concurrent_id], expected=1)["error"]["code"] == "event_forgotten", "forgotten event cannot be re-extracted")
        raw = "I prefer text without a speaker label. 中文😀".encode("utf-8")
        first = json.loads(process(["session-capture", "--source", "alpha", "--label", "legacy"], raw).stdout)
        again = json.loads(process(["session-capture", "--source", "alpha", "--label", "legacy"], raw).stdout)
        check(first["event_id"] == again["event_id"] and again["duplicate"], "legacy raw capture no longer uses second-resolution overwrite identity")
        check(cli("extract", ["--event", first["event_id"]])["status"] == "no_matches", "legacy unknown-role text is not attributed to the user")
        check(sql("PRAGMA integrity_check") == "ok", "isolated database remains structurally valid")
        print(f"N43 real-process integration: {checks} checks passed; observed lock retries={retries}; no live provider or user data.", flush=True)


if __name__ == "__main__":
    main()
