"""N46F CJK literal recall: real-process checks for both retrieval paths.

memory_read (instr substring) and search (FTS5 + supplemental literal append)
are exercised against the actual prebuilt/CI binary with a unique temp brain
and isolated data root. Synthetic data only; no provider, no user data.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import uuid

FIXTURE_QUOTE = "我偏好在这个测试项目中使用日志前缀QBCJKfixture，并且保持原文。"


class CheckFailure(AssertionError):
    pass


def status_counts(checks: list[dict]) -> dict:
    counts = Counter(item["status"] for item in checks)
    if set(counts) - {"PASS", "FAIL"}:
        raise ValueError("Unexpected CJK check status")
    return {"total": len(checks), "pass": counts["PASS"], "fail": counts["FAIL"]}


def add_source_provenance(report: dict, script: Path) -> None:
    report.update(native_windows=os.name == "nt", real_agent_verified=False, live_provider_verified=False)
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       cwd=script.parent.parent, text=True,
                                       stderr=subprocess.DEVNULL).strip()
        clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--"],
                               cwd=script.parent.parent, stderr=subprocess.DEVNULL).returncode == 0
        report.update(source_commit=head if clean else None, head_commit=head,
                      tracked_tree_clean=clean)
    except (OSError, subprocess.SubprocessError):
        report.update(source_commit=None, head_commit=None, tracked_tree_clean=False)


def run(args: argparse.Namespace, checks: list[dict] | None = None,
        commands: list[dict] | None = None) -> dict:
    binary = args.binary.resolve()
    script = Path(__file__).resolve()
    checks = [] if checks is None else checks
    commands = [] if commands is None else commands

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        if not ok:
            failure = CheckFailure(detail or name)
            failure.partial_checks = list(checks)
            raise failure

    with tempfile.TemporaryDirectory(prefix="qbrain-n46f-") as tmp:
        root = Path(tmp)
        brain = "cjk-" + uuid.uuid4().hex[:12]
        env = {k: v for k, v in os.environ.items()
               if not k.upper().startswith(("QBRAIN", "OPENAI", "ANTHROPIC"))
               and k.upper() not in {"HOME", "USERPROFILE", "LOCALAPPDATA", "APPDATA"}}
        env.update({k: str(root) for k in ("HOME", "USERPROFILE", "LOCALAPPDATA", "APPDATA")})
        env["QBRAIN_EMBED_MOCK"] = "1"

        def process(arguments: list[str], payload: bytes | None = None):
            try:
                result = subprocess.run([str(binary), *arguments], input=payload,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        cwd=root, env=env, timeout=60, check=False)
            except (OSError, subprocess.TimeoutExpired) as error:
                commands.append({"arguments": arguments, "exit_code": None,
                                 "error_type": type(error).__name__})
                raise
            commands.append({"arguments": arguments, "exit_code": result.returncode})
            return result

        def cli(arguments: list[str], payload: bytes | None = None):
            r = process(arguments, payload)
            if r.returncode != 0:
                raise CheckFailure(f"cli {arguments[:2]} exit {r.returncode}: "
                                   f"{r.stderr.decode('utf-8', 'replace')[:300]}")
            text = r.stdout.decode("utf-8")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"raw_text": text}  # init/delete and other text commands

        def put(slug: str, title: str, body: str) -> None:
            body_file = root / f"body-{uuid.uuid4().hex[:8]}.md"
            body_file.write_text(body, encoding="utf-8")
            cli(["put", "--brain", brain, "--slug", slug, "--title", title,
                 "--file", str(body_file), "--json"])
            body_file.unlink()

        def search(query: str, limit: int | None = None) -> list:
            argv = ["search", query, "--brain", brain, "--json", "--no-vector"]
            if limit is not None:
                argv += ["--limit", str(limit)]
            return cli(argv)

        def memory_read(query: str, limit: int | None = None,
                        max_bytes: int | None = None) -> dict:
            argv = ["memory", "read", "--brain", brain, "--query", query]
            if limit is not None:
                argv += ["--limit", str(limit)]
            if max_bytes is not None:
                argv += ["--max-bytes", str(max_bytes)]
            return cli(argv)

        def sql(statement: str, parameters: tuple = ()) -> None:
            conn = sqlite3.connect(db_path())
            conn.execute(statement, parameters)
            conn.commit()
            conn.close()

        def mcp(calls: list[tuple[str, object]], *, allow_write: bool = False):
            messages = [{"jsonrpc": "2.0", "id": 0, "method": "initialize",
                         "params": {"protocolVersion": "2024-11-05"}},
                        {"jsonrpc": "2.0", "method": "notifications/initialized"}]
            messages += [{"jsonrpc": "2.0", "id": i, "method": "tools/call",
                          "params": {"name": name, "arguments": arguments}}
                         for i, (name, arguments) in enumerate(calls, 1)]
            p = process(["serve", "--brain", brain,
                         *(["--allow-write"] if allow_write else [])],
                        b"\n".join(json.dumps(m, ensure_ascii=False).encode("utf-8")
                                   for m in messages) + b"\n")
            if p.returncode != 0:
                raise CheckFailure(f"mcp serve exit {p.returncode}")
            rows = [json.loads(line) for line in p.stdout.decode("utf-8").splitlines()]
            if len(rows) != len(calls) + 1:
                raise CheckFailure("MCP NDJSON response count")
            return [r["result"] for r in rows[1:]]

        def db_path() -> Path:
            data_root = root if os.name == "nt" else root / ".local" / "share"
            return data_root / "Qbrain" / "brains" / brain / "brain.db"

        # --- setup: fixture page + fixture memory quote -------------------
        cli(["init", "--brain", brain, "--no-default"])
        put("cjk-fixture", "中文验收夹具", FIXTURE_QUOTE)
        capture = {"session_id": "n46f-" + brain, "fragment_id": "f1",
                   "messages": [{"role": "user", "content": FIXTURE_QUOTE}]}
        event = cli(["memory", "capture", "--brain", brain, "--manual"],
                    json.dumps(capture, ensure_ascii=False).encode("utf-8"))
        check("unextracted_archive_not_memory", memory_read("日志前缀")["items"] == [])
        cli(["memory", "extract", "--brain", brain, "--event", event["event_id"]])

        # --- memory path (instr substring; algorithm unchanged) -----------
        check("memory_single_char", any(
            i["quote"] == FIXTURE_QUOTE for i in memory_read("缀")["items"]),
            "单字 '缀' 取回完整原话")
        check("memory_double_char", any(
            i["quote"] == FIXTURE_QUOTE for i in memory_read("前缀")["items"]),
            "双字 '前缀' 取回完整原话")
        check("memory_mixed_ascii", any(
            i["quote"] == FIXTURE_QUOTE for i in memory_read("前缀QBCJKfixture")["items"]),
            "混合英文 '前缀QBCJKfixture' 取回完整原话")
        check("memory_noncontiguous_miss", memory_read("日志 前缀")["items"] == [],
              "非连续子串 '日志 前缀' 不命中（子串语义，非分词）")
        mcp_rows = mcp([("memory_read", {"query": "日志前缀"})])
        mcp_items = json.loads(mcp_rows[0]["content"][-1]["text"])["items"]
        check("mcp_memory_read_hit", any(
            i["quote"] == FIXTURE_QUOTE for i in mcp_items)
            and all(i.get("source_id") == "default" for i in mcp_items),
            "MCP memory_read '日志前缀' 命中并带 source 字段")

        # --- search path: the N46F supplemental behavior ------------------
        check("search_phrase_hits", any(
            h["slug"] == "cjk-fixture" for h in search("日志前缀")),
            "search '日志前缀' 命中（旧版 FTS5 漏掉的基线用例）")
        check("search_single_char_hits", any(
            h["slug"] == "cjk-fixture" for h in search("缀")), "search 单字 '缀' 命中")

        put("cjk-ext", "扩展区", "生僻字夹具𠀀𫠛正文")
        check("search_ext_block_hits", any(
            h["slug"] == "cjk-ext" for h in search("𠀀𫠛")), "扩展B区汉字子串命中")
        put("cjk-kana", "仮名", "かなテスト本文カナ")
        put("cjk-hangul", "한글", "한국어 텍스트 본문")
        check("search_kana_hits", any(h["slug"] == "cjk-kana" for h in search("かな")),
              "假名子串命中")
        check("search_hangul_hits", any(h["slug"] == "cjk-hangul" for h in search("본문")),
              "韩文子串命中")

        put("fts-token", "独立token", "前缀")
        put("substr-only", "长句内嵌", "我维护很长的句子其中包含日志前缀管理规则以及其他内容")
        slugs = [h["slug"] for h in search("前缀")]
        check("append_beside_fts", "fts-token" in slugs and "substr-only" in slugs,
              f"FTS 命中与子串命中同时返回: {slugs}")
        check("dedupe_by_page", len(slugs) == len(set(slugs)), "同一页面不重复出现")

        sql("INSERT INTO config(key,value) VALUES('mcp.allowed_sources','alpha') "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value")
        put_result = mcp([("put_page", {"slug": "cjk-fixture", "title": "alpha副本",
                                        "body": "阿尔法来源的日志前缀正文",
                                        "source_id": "alpha", "type": "note"})],
                         allow_write=True)
        check("mcp_put_alpha_ok", not put_result[0].get("isError", False),
              "MCP put_page 写入 alpha 来源")
        alpha = mcp([("search", {"query": "阿尔法", "source_id": "alpha",
                                 "no_vector": True})])
        alpha_hits = json.loads(alpha[0]["content"][-1]["text"])
        check("source_filter_alpha", any(h["slug"] == "cjk-fixture"
                                         and h["source_id"] == "alpha"
                                         for h in alpha_hits)
              and all(h["source_id"] == "alpha" for h in alpha_hits),
              "同名不同来源按 source_id 过滤")
        denied = mcp([("search", {"query": "日志前缀", "source_id": "beta",
                                  "no_vector": True})])
        check("source_denied", denied[0].get("isError", False), "未允许的来源 beta 被拒绝")

        put("like-special", "特殊字符", "大促折扣50%_off\\免运费以及 'or 1=1; -- 结束")
        check("like_special_literal", any(h["slug"] == "like-special"
                                          for h in search("折扣50%_off\\免")),
              "LIKE 特殊字符按字面命中")
        put("sql-style", "注入样式", "注入'; DROP TABLE pages;--日志前缀测试")
        check("sql_style_literal", any(h["slug"] == "sql-style"
                                       for h in search("'; DROP TABLE pages;--日志前缀")),
              "SQL 样式文本按字面命中且无错误")
        check("db_alive_after_sql", any(h["slug"] == "cjk-fixture"
                                        for h in search("日志前缀")),
              "SQL 样式查询后数据库完好")

        put("title-only", "标题里有前缀登记", "正文完全不含相关词")
        check("title_match", any(h["slug"] == "title-only" for h in search("前缀登记")),
              "仅标题含子串也命中")
        put("中文slug测试", "slug夹具", "正文没有关键词")
        check("slug_match", any(h["slug"] == "中文slug测试" for h in search("中文slug")),
              "仅 slug 含子串也命中")

        put("ascii-token", "ASCII fixture", "QBCJKfixture")
        check("ascii_fts_still_works", any(h["slug"] == "ascii-token"
                                           for h in search("QBCJKfixture")),
              "纯 ASCII 查询仍走原 FTS 行为")
        put("ascii-only-body", "纯英文", "plain ascii body without cjk tokens")
        check("ascii_no_supplement_noise", all(h["slug"] != "ascii-only-body"
                                               for h in search("scii bod")),
              "纯 ASCII 跨词面子串不引入补充噪音")

        put("order-old", "顺序旧", "顺序检查包含日志前缀的旧页面")
        put("order-new", "顺序新", "顺序检查包含日志前缀的新页面")
        sql("UPDATE pages SET updated_at=? WHERE source_id='default' AND slug=?", ("2026-01-01 00:00:00", "order-old"))
        sql("UPDATE pages SET updated_at=? WHERE source_id='default' AND slug=?", ("2026-01-02 00:00:00", "order-new"))
        ordered = [h["slug"] for h in search("日志前缀") if h["slug"].startswith("order-")]
        check("stable_order", ordered == ["order-new", "order-old"],
              f"updated_at DESC 稳定排序: {ordered}")

        check("search_limit", len(search("日志前缀", limit=1)) == 1, "search limit=1 生效")
        long_quote = "我偏好超长原话" + "详" * 1200 + "日志前缀结束"
        cap = {"session_id": "n46f-long", "fragment_id": "f2",
               "messages": [{"role": "user", "content": long_quote}]}
        ev2 = cli(["memory", "capture", "--brain", brain, "--manual"],
                  json.dumps(cap, ensure_ascii=False).encode("utf-8"))
        cli(["memory", "extract", "--brain", brain, "--event", ev2["event_id"]])
        small = memory_read("超长原话", limit=5, max_bytes=512)
        check("memory_limit_and_bytes", len(small["items"]) <= 5
              and small.get("truncated") is True, "memory read limit 与 max_bytes 预算生效")

        put("update-me", "更新前", "更新前的内容包含旧关键词甲乙丙")
        put("update-me", "更新后", "更新后的内容包含新关键词丁戊己")
        check("update_visible", any(h["slug"] == "update-me" for h in search("丁戊己")),
              "更新后的新内容可检索")
        check("update_old_gone", all(h["slug"] != "update-me" for h in search("甲乙丙")),
              "更新前的旧内容不再命中")

        cli(["delete", "--brain", brain, "update-me"])
        check("soft_delete_excluded", all(h["slug"] != "update-me"
                                          for h in search("丁戊己")),
              "软删除页面从 search 排除")

        sql("DELETE FROM pages WHERE slug = 'substr-only'")
        check("hard_delete_excluded", all(h["slug"] != "substr-only"
                                          for h in search("日志前缀")),
              "物理删除行后 search 正常且不返回")

        cli(["memory", "forget", "--brain", brain, "--event", ev2["event_id"]])
        check("memory_forget", memory_read("超长原话")["items"] == [],
              "遗忘事件后 memory read 不再返回")

        # Expiry and evidence integrity remain distinct from page-search matching.
        sql("UPDATE memory_items SET expires_at=1 WHERE event_id=?", (event["event_id"],))
        check("expired_memory_excluded", memory_read("QBCJKfixture")["items"] == [])
        sql("UPDATE memory_items SET expires_at=0 WHERE event_id=?", (event["event_id"],))
        with closing(sqlite3.connect(db_path())) as db:
            archived = db.execute("SELECT p.body FROM pages p JOIN memory_events e ON e.page_id=p.id WHERE e.event_id=?", (event["event_id"],)).fetchone()[0]
        sql("UPDATE pages SET body=? WHERE id=(SELECT page_id FROM memory_events WHERE event_id=?)", (archived + " ", event["event_id"]))
        check("tampered_evidence_excluded", memory_read("QBCJKfixture")["items"] == [])
        sql("UPDATE pages SET body=? WHERE id=(SELECT page_id FROM memory_events WHERE event_id=?)", (archived, event["event_id"]))
        check("exact_evidence_restored", len(memory_read("QBCJKfixture")["items"]) == 1)
        check("no_implicit_traditional_conversion", memory_read("日誌前綴")["items"] == [])

        def db_digest() -> str:
            parts = []
            for suffix in ("", "-wal", "-shm"):
                p = Path(str(db_path()) + suffix)
                if p.exists():
                    parts.append(hashlib.sha256(p.read_bytes()).hexdigest())
            return "|".join(parts)

        before = db_digest()
        search("日志前缀")
        memory_read("日志前缀")
        check("read_does_not_write", db_digest() == before, "读操作不改变数据库文件")

    report = {
        "suite": "n46f_cjk_recall", "result": "PASS",
        "binary": str(binary),
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
        "fixture_quote": FIXTURE_QUOTE, "checks": checks,
        "check_count": len(checks),
        "counts": status_counts(checks), "commands": commands,
    }
    add_source_provenance(report, script)
    return report


def main() -> int:
    # Windows redirected Python streams may default to cp1252. Configure only
    # this process, preserving UTF-8 JSON/Chinese diagnostics under PowerShell.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--source-commit", help="Declared package source only; never replaces observed Git provenance")
    parser.add_argument("--expected-binary-sha256")
    parser.add_argument("--require-windows", action="store_true")
    args = parser.parse_args()
    checks: list[dict] = []
    commands: list[dict] = []
    try:
        if args.require_windows and os.name != "nt":
            raise CheckFailure("Native Windows execution required")
        if args.expected_binary_sha256 and hashlib.sha256(args.binary.read_bytes()).hexdigest() != args.expected_binary_sha256:
            raise CheckFailure("Executable SHA256 mismatch; nothing executed")
        report = run(args, checks, commands)
        failed = 0
    except (AssertionError, OSError, ValueError, KeyError, TypeError,
            subprocess.SubprocessError) as failure:
        failed = 1
        if not checks or checks[-1]["status"] != "FAIL":
            checks.append({"name": "execution_error", "status": "FAIL",
                           "detail": type(failure).__name__})
        partial = checks
        report = {
            "suite": "n46f_cjk_recall", "result": "FAIL", "error": str(failure),
            "binary": str(args.binary.resolve()),
            "binary_sha256": (hashlib.sha256(args.binary.read_bytes()).hexdigest() if args.binary.is_file() else None),
            "script_sha256": hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest(),
            "fixture_quote": FIXTURE_QUOTE, "checks": partial,
            "check_count": len(partial),
            "counts": status_counts(partial), "commands": commands,
        }
        add_source_provenance(report, Path(__file__).resolve())
        print(f"N46F CJK recall FAILED: {failure}", file=sys.stderr)
    report["declared_package_source"] = args.source_commit
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    print(text)
    for c in report["checks"]:
        print(f"{c['status']} :: {c['name']} :: {c['detail']}")
    print(f"N46F CJK recall: {report['check_count']} checks, result={report['result']}")
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
