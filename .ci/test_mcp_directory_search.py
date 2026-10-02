"""N49D actual CLI/stdio and native-Windows authenticated HTTP checks.

Uses disposable SQLite, built-in embedding mocks, and an isolated ordinary
loopback embedding-provider fixture on Windows. Explicit checks survive python
-O, and raw evidence remains bounded on partial failure. Linux retains functional
mock-vector coverage without a provider-network/count claim. In-process remote
behavior is native unit coverage, never an actual HTTP transport pass.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import socketserver
import sqlite3
import struct
import tempfile
import threading
import time
import traceback

# Shared, reviewed process-tree/deadline owner; no separate cleanup mechanism.
from run_n49d_qualification import OwnedChild, OwnedChildError

BASE_COMMIT = "cfe1ef58e244b51092c2248804b663b6c28913d7"
# Fixed accepted-base registration-name inventory: handlers.cpp register_one calls
# plus memory_ops.cpp/context_ops.cpp Scope registrations, exactly 112 names.
BASE_NAMES = set("""
add_link add_tag add_timeline_entry advisor cancel_job capture chronicle_backfill chronicle_day
chronicle_last_seen chronicle_on_this_day chronicle_since code_blast code_callees code_callers
code_def code_flow code_refs code_traversal_cache_clear context_read context_write delete_page
doctor_remediate extract_facts file_list file_upload file_url find_anomalies find_contradictions
find_experts find_orphans find_trajectory forget_fact get_active_schema_pack get_backlinks
get_brain_identity get_calibration_profile get_chunks get_health get_ingest_log get_job
get_job_progress get_links get_page get_raw_data get_recent_salience get_recent_transcripts
get_skill get_stats get_status_snapshot get_tags get_timeline get_versions list_brain_skillpack
list_brains list_facts list_job_messages list_jobs list_link_sources list_pages list_schema_packs
list_skills log_ingest memory_read memory_write ontology_conflicts ontology_dimensions ontology_get
ontology_propose pause_job purge_deleted_pages put_page put_raw_data query recall reload_schema_pack
remove_link remove_tag replay_job resolve_slugs restore_page resume_job retry_job revert_version
run_doctor run_dream run_onboard run_skillopt schema_apply_mutations schema_explain_type schema_graph
schema_lint schema_review_orphans schema_stats search search_by_image send_job_message sources_add
sources_list sources_remove sources_status submit_agent submit_job sync_brain takes_calibration
takes_list takes_scorecard takes_search think traverse_graph volunteer_chronicle volunteer_context whoami
""".split())
MEMORY_NAMES = {"search", "get_page", "memory_read", "memory_write", "context_read", "context_write"}
BRAIN = "n49d-fixture"
STREAM_CAP = 2 * 1024 * 1024
TOKEN = "n49d-synthetic-local-token-0123456789"


def wire(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Evidence:
    def __init__(self, output: Path):
        self.output = output
        output.mkdir(parents=True, exist_ok=False)
        (output / "raw").mkdir()
        self.checks: list[dict] = []
        self.commands: list[dict] = []
        self.exchanges: list[dict] = []
        self.children: list[OwnedProcess] = []
        self.serial = 0
        self.path_lock = threading.Lock()

    def need(self, condition: bool, label: str) -> None:
        self.checks.append({"name": label, "passed": bool(condition)})
        if not condition:
            raise ValueError(label)

    def path(self, kind: str) -> Path:
        with self.path_lock:
            self.serial += 1
            return self.output / "raw" / f"{self.serial:04d}-{kind}"

    def blob(self, path: Path, data: bytes) -> dict:
        if len(data) > STREAM_CAP:
            raise ValueError("raw evidence stream budget exceeded")
        path.write_bytes(data)
        return {"path": path.relative_to(self.output).as_posix(), "bytes": len(data), "sha256": sha(data)}

    def file(self, path: Path) -> dict:
        # Process output is already preserved on disk before validation.
        size = path.stat().st_size
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(65536), b""):
                digest.update(chunk)
        return {"path": path.relative_to(self.output).as_posix(), "bytes": size, "sha256": digest.hexdigest()}


class OwnedProcess:
    """Evidence adapter over the single shared child-tree owner."""
    def __init__(self, ev: Evidence, argv: list[str], cwd: Path, env: dict[str, str],
                 data: bytes = b"", timeout: float = 30):
        self.ev = ev
        self.started = time.monotonic()
        adapter_deadline = self.started + timeout
        self.proc = None
        self.owner = None
        self.closed = False
        self.stdin_path = ev.path("stdin.bin")
        self.stdout_path = ev.path("stdout.bin")
        self.stderr_path = ev.path("stderr.bin")
        self.record = {"argv": argv, "cwd": str(cwd), "status": "starting",
                       "stdin": ev.blob(self.stdin_path, data)}
        ev.commands.append(self.record)
        try:
            remaining = adapter_deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("process evidence setup exceeded whole deadline")
            with self.stdin_path.open("rb") as source:
                self.owner = OwnedChild(argv, cwd, env, stdin=source,
                                        stdout_path=self.stdout_path, stderr_path=self.stderr_path,
                                        timeout=remaining, stream_cap=STREAM_CAP)
            self.owner.deadline = min(self.owner.deadline, adapter_deadline)
            self.proc = self.owner.proc
            ev.children.append(self)
            self.record.update(status="running", pid=self.proc.pid)
        except OwnedChildError as error:
            self.owner = error.owner
            self.proc = getattr(self.owner, "proc", None)
            self._terminal("spawn_failed")
            raise
        except BaseException:
            self.record.update(status="spawn_failed", stable=False)
            raise

    def _check_finalization_deadline(self) -> None:
        now = time.monotonic()
        self.record["elapsed_seconds"] = round(now - self.started, 6)
        if now >= self.owner.deadline:
            self.record.update(status="failed_finalization_deadline", finalization_classification="timeout")
            raise TimeoutError("process evidence finalization exceeded whole deadline")

    def _terminal(self, status: str, require_deadline: bool = False) -> None:
        if self.closed:
            return
        terminal = getattr(self.owner, "result", None)
        stable = bool(getattr(self.owner, "stable", False))
        self.record.update(status=status, ownership=terminal, stable=stable,
                           exit=terminal.get("exit") if isinstance(terminal, dict) else None,
                           elapsed_seconds=round(time.monotonic() - self.started, 6))
        for key, path in (("stdout", self.stdout_path), ("stderr", self.stderr_path)):
            if stable:
                self.record[key] = self.ev.file(path)
            else:
                # Retain partial evidence, never claim mutable bytes are finalized.
                self.record[key] = {"path": path.relative_to(self.ev.output).as_posix(),
                                    "stable": False, "present": path.is_file()}
        self.closed = True
        if require_deadline:
            self._check_finalization_deadline()

    def budget(self) -> None:
        try:
            self.owner.check_budget()
        except BaseException:
            self._terminal("failed_budget_or_cleanup")
            raise

    def stop(self, reason: str) -> None:
        if self.closed:
            return
        try:
            terminal = self.owner.stop(reason)
            self.ev.need(self.owner.stable and terminal.get("cleanup_ok") is True
                         and terminal.get("classification") == "stopped",
                         "owned server tree and output writers terminate before finalization")
            self._terminal(reason, require_deadline=True)
        except BaseException:
            self._terminal("failed_cleanup")
            raise

    def wait(self, expected: int = 0, timeout: float | None = None) -> bytes:
        try:
            terminal = self.owner.wait(expected=expected, timeout=timeout)
            self.ev.need(self.owner.stable and terminal.get("cleanup_ok") is True
                         and terminal.get("classification") == "passed" and terminal.get("exit") == expected,
                         "whole child tree exits within its deadline before stable evidence success")
            self._terminal("completed", require_deadline=True)
            data = self.stdout_path.read_bytes()
            self._check_finalization_deadline()
            return data
        except BaseException:
            self._terminal("failed_process")
            raise


class Fixture:
    def __init__(self, ev: Evidence, binary: Path, root: Path):
        self.ev, self.binary, self.root = ev, binary, root
        # No user credentials, source, selected brain, provider or PG settings enter a child.
        self.env = {k: v for k, v in os.environ.items() if not k.upper().startswith(
            ("QBRAIN", "PG", "OPENAI", "ANTHROPIC", "AZURE_OPENAI", "GEMINI", "GOOGLE_API", "GH_TOKEN", "GITHUB_TOKEN"))}
        self.env.update(HOME=str(root), USERPROFILE=str(root), LOCALAPPDATA=str(root), APPDATA=str(root),
                        XDG_DATA_HOME=str(root / ".local/share"), QBRAIN_EMBED_MOCK="1")
        data_root = root if os.name == "nt" else root / ".local/share"
        self.dbpath = data_root / "Qbrain" / "brains" / BRAIN / "brain.db"

    def child(self, arguments: list[str], data: bytes = b"", extra: dict | None = None,
              timeout: float = 30) -> OwnedProcess:
        return OwnedProcess(self.ev, [str(self.binary), *arguments, "--brain", BRAIN], self.root,
                            {**self.env, **(extra or {})}, data, timeout)

    def run(self, arguments: list[str], data: bytes = b"", extra: dict | None = None) -> bytes:
        return self.child(arguments, data, extra).wait()

    def sql(self, statement: str, params: tuple = ()) -> list:
        with closing(sqlite3.connect(self.dbpath)) as db:
            rows = db.execute(statement, params).fetchall()
            db.commit()
            return rows

    def snapshot(self) -> str:
        with closing(sqlite3.connect(self.dbpath)) as db:
            tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            rows = {table: sorted(db.execute('SELECT * FROM "' + table.replace('"', '""') + '"').fetchall(), key=repr)
                    for table in tables}
        return sha(repr(rows).encode("utf-8"))

    def seed(self) -> None:
        self.run(["init", "--no-default"])
        self.ev.need(self.dbpath.is_file(), "actual executable initializes isolated SQLite fixture")
        for key, value in (("embed.auto", "false"), ("mcp.allowed_sources", "alpha,0,1,7,missing")):
            self.sql("INSERT INTO config(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
        for source in ("alpha", "beta", "0", "1", "7"):
            self.sql("INSERT INTO sources(id,name) VALUES(?,?)", (source, source))
        # Existing built-in mock contract: one text returns [UTF8-byte-length % 17 + 1, 1, 1].
        # Matching model/dimension metadata is preloaded directly, never a live provider request.
        vector = struct.pack("<fff", len(b"vectoronlyquery") % 17 + 1, 1, 1)
        pages = [("docs/a", "note", "needle root"), ("docs/sub/b", "note", "needle nested"),
                 ("docs-neighbor/c", "note", "needle neighbor"), ("Docs/case", "note", "needle case"),
                 ("docs/tool", "skill", "needle skill"), ("docs/session", "session_fragment", "needle memory"),
                 ("docs/deleted", "note", "needle deleted"), ("文档/深/页", "note", "这里有针")]
        with closing(sqlite3.connect(self.dbpath)) as db:
            for source in ("default", "alpha", "beta", "0", "1", "7"):
                for slug, kind, body in pages:
                    page = db.execute("INSERT INTO pages(source_id,slug,type,title,body) VALUES(?,?,?,?,?)", (source, slug, kind, slug, body)).lastrowid
                    db.execute("INSERT INTO content_chunks(page_id,chunk_index,text,embedding,dim,model) VALUES(?,0,?,?,3,'mock-embedding')", (page, body, vector))
            db.execute("UPDATE pages SET deleted_at='2026-10-01' WHERE slug='docs/deleted'")
            db.commit()

    def cli(self, query: str, uri: str | None, vector: bool = False, mode: str = "balanced") -> list:
        # Accepted CLI scopes via URI; it has no --source search argument.
        # The no-URI CLI remains intentionally local and cross-source.
        argv = ["search", "--query", query, "--limit", "20", "--mode", mode, "--json"]
        if uri is not None:
            argv += ["--uri", uri]
        if not vector:
            argv += ["--no-vector"]
        return json.loads(self.run(argv))

    def stdio(self, profile: str, messages: list[bytes], extra: dict | None = None) -> list[dict]:
        raw = self.run(["serve", "--tool-profile", profile], b"\n".join(messages) + b"\n", extra)
        lines = raw.splitlines()
        self.ev.need(len(lines) == len(messages), "stdio returns one response per non-notification request")
        return [json.loads(line) for line in lines]


class Http:
    def __init__(self, fixture: Fixture, profile: str, extra: dict | None = None):
        self.fixture, self.ev = fixture, fixture.ev
        with closing(socket.socket()) as bound:
            bound.bind(("127.0.0.1", 0))
            self.port = bound.getsockname()[1]
        self.process = fixture.child(["serve", "--http", "--port", str(self.port), "--tool-profile", profile],
                                     extra={**(extra or {}), "QBRAIN_MCP_TOKEN": TOKEN}, timeout=120)
        try:
            deadline = time.monotonic() + 10
            while True:
                self.process.budget()
                if self.process.proc.poll() is not None:
                    self.process.stop("failed_startup")
                    raise ValueError("HTTP server exited before readiness")
                try:
                    with socket.create_connection(("127.0.0.1", self.port), timeout=1):
                        pass
                    break
                except (ConnectionRefusedError, TimeoutError, ConnectionResetError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("HTTP listener readiness timeout")
                    time.sleep(0.05)
        except BaseException:
            self.process.stop("failed_startup")
            raise

    def exchange(self, body: bytes, token: str | None = TOKEN, expected: int = 200) -> dict:
        self.process.budget()
        auth = b"" if token is None else b"Authorization: Bearer " + token.encode("ascii") + b"\r\n"
        raw = b"POST / HTTP/1.1\r\nHost: 127.0.0.1\r\n" + auth + b"Content-Type: application/json\r\nContent-Length: " + str(len(body)).encode("ascii") + b"\r\nConnection: close\r\n\r\n" + body
        rec = {"transport": "loopback_http", "port": self.port,
               "request": self.ev.blob(self.ev.path("http-request.bin"), raw), "status": "pending"}
        self.ev.exchanges.append(rec)
        received = bytearray()
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=2) as conn:
                conn.settimeout(5)
                conn.sendall(raw)
                while True:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    if len(received) + len(chunk) > STREAM_CAP:
                        raise ValueError("HTTP response budget exceeded")
                    received.extend(chunk)
            headers, content = bytes(received).split(b"\r\n\r\n", 1)
            status = int(headers.split(b"\r\n", 1)[0].split()[1])
            rec.update(status="completed", http_status=status)
            self.ev.need(status == expected, f"HTTP expected status {expected}, got {status}")
            return json.loads(content) if status == 200 else {}
        except BaseException as error:
            rec.update(status="failed", failure=type(error).__name__)
            raise
        finally:
            rec["response"] = self.ev.blob(self.ev.path("http-response.bin"), bytes(received))

    def close(self, success: bool) -> None:
        if success:
            self.process.budget()
            self.ev.need(self.process.proc.poll() is None, "HTTP server remains alive until owned cleanup")
        self.process.stop("server_stopped_after_checks" if success else "server_stopped_after_failure")


def request(args: dict, name: str = "search", identity: int = 49) -> bytes:
    return wire({"jsonrpc": "2.0", "id": identity, "method": "tools/call",
                 "params": {"name": name, "arguments": args}})


def payload(ev: Evidence, response: dict, error: bool = False):
    ev.need("error" not in response and "result" in response, "decoded arguments remain tool-layer responses")
    result = response["result"]
    ev.need(result.get("isError") is error, "MCP tool error classification")
    return json.loads(result["content"][-1]["text"])


def source_hits(ev: Evidence, response: dict, source: str, expected: set[str] | None = None) -> list:
    hits = payload(ev, response)
    ev.need(isinstance(hits, list) and bool(hits), "source fixture returns positive array evidence")
    ev.need(all(hit["source_id"] == source for hit in hits), "every result retains authorized effective source")
    if expected is not None:
        ev.need({hit["slug"] for hit in hits} == expected, "exact scoped membership")
    return hits


def uri_error(ev: Evidence, response: dict) -> None:
    value = payload(ev, response, error=True)
    ev.need(value["error"]["code"] == "invalid_argument" and value["error"]["field"] == "uri", "URI-specific invalid_argument")
    ev.need(len(wire(response)) < 512 and "hits" not in value, "bounded URI rejection without hits or broad fallback")


def exercise(f: Fixture, profile: str, transport: str, cli: dict, http: Http | None = None) -> None:
    ev = f.ev
    def send(messages: list[bytes], extra: dict | None = None) -> list[dict]:
        if http is None:
            return f.stdio(profile, messages, extra)
        if extra:
            raise ValueError("HTTP ambient source requires a separately configured server")
        return [http.exchange(message) for message in messages]
    listing = wire({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    listed = send([listing])[0]["result"]["tools"]
    names = [tool["name"] for tool in listed]
    ev.need(set(names) == (BASE_NAMES if profile == "full" else MEMORY_NAMES) and len(names) == len(set(names)), f"{transport}/{profile} exact base tool-name set")
    search = next(tool for tool in listed if tool["name"] == "search")["inputSchema"]
    ev.need(search["properties"]["uri"].get("type") == "string" and "uri" not in search.get("required", []), "optional URI string schema")
    scenarios = [
        ("default", "default", "resources/docs/", "needle", False, "balanced", {"docs/a", "docs/sub/b"}),
        ("alpha", "alpha", "resources/docs/", "needle", False, "balanced", {"docs/a", "docs/sub/b"}),
        ("root", "alpha", "resources/", "needle", False, "balanced", {"docs/a", "docs/sub/b", "docs-neighbor/c", "Docs/case"}),
        ("skills", "alpha", "skills/docs/", "needle", False, "balanced", {"docs/tool"}),
        ("memories", "alpha", "memories/docs/", "needle", False, "balanced", {"docs/session"}),
        ("unicode", "alpha", "resources/文档/", "针", False, "balanced", {"文档/深/页"}),
        ("vector", "alpha", "resources/docs/", "vectoronlyquery", True, "balanced", {"docs/a", "docs/sub/b"}),
        ("no_vector", "alpha", "resources/docs/", "vectoronlyquery", False, "balanced", set()),
        ("conservative", "alpha", "resources/docs/", "vectoronlyquery", True, "conservative", set()),
        ("empty", "alpha", "resources/absent/", "needle", False, "balanced", set()),
        ("legacy", "alpha", None, "needle", False, "balanced", None),
    ]
    calls = []
    for label, source, scope, query, vector, mode, expected in scenarios:
        args = {"query": query, "source_id": source, "no_vector": not vector, "limit": 20, "mode": mode}
        if scope is not None:
            args["uri"] = f"qbrain://{source}/{scope}"
        calls.append(request(args))
    for scenario, response in zip(scenarios, send(calls)):
        label, source, _, _, _, _, expected = scenario
        hits = payload(ev, response)
        if label != "legacy":
            ev.need(hits == cli[label], f"{transport}/{profile}/{label} ordered complete CLI/MCP result-object equality")
        else:
            # Fixed-base byte/serialization equality lives in the native unit test.
            # No-URI CLI is cross-source, so it is deliberately not this oracle.
            ev.need(bool(hits) and all(set(hit) == {"rank", "source_id", "page_id", "slug", "title", "score", "rerank_score", "snippet"} for hit in hits), "no-URI MCP preserves the base eight-field result shape")
            ev.need(len(response["result"]["content"]) == 2, "no-URI MCP retains text plus serialized result blocks")
        ev.need(all(hit["source_id"] == source for hit in hits), "CLI/MCP source isolation")
        if expected is not None:
            ev.need({hit["slug"] for hit in hits} == expected, f"{label} exact recursive membership")
        if not hits:
            ev.need(response["result"]["content"][0]["text"] == "(no results)\n", "successful empty result text shape")
    uri = "qbrain://alpha/resources/docs/"
    bad_uris = [None, True, 7, 1.5, ["private-uri-marker"], {"private-uri-marker": 1}, "", "private-uri-marker",
                "qbrain://alpha/resources/docs", "qbrain://alpha/unknown/docs/", "qbrain://alpha/resources/../",
                "qbrain://alpha/resources/a%2fb/", "qbrain://alpha/resources/a%5cb/", "qbrain://alpha/resources//",
                "qbrain://alpha/resources/docs//", "qbrain://alpha/resources/a\\b/", "qbrain://ALPHA/resources/docs/",
                "QBRAIN://alpha/resources/docs/", "qbrain://beta/resources/docs/", "qbrain://missing/resources/docs/",
                "qbrain://alpha/resources/" + "x" * 9000 + "/", "qbrain://alpha/resources/a\0b/"]
    for value, response in zip(bad_uris, send([request({"query": "needle", "source_id": "alpha", "uri": value}) for value in bad_uris])):
        uri_error(ev, response)
        if isinstance(value, str) and len(value) > 4:
            ev.need(value not in json.dumps(response, ensure_ascii=False), "invalid URI input not echoed")
    # The URI cannot pick a source; omission still means default.
    uri_error(ev, send([request({"query": "needle", "uri": uri})])[0])
    for raw_source, effective in ((None, "default"), ("ALPHA", "alpha"), (True, "1"), (False, "0"), (7, "7")):
        args = {"query": "needle", "source_id": raw_source, "no_vector": True, "limit": 20}
        old, scoped = send([request(args), request({**args, "uri": f"qbrain://{effective}/resources/docs/"})])
        source_hits(ev, old, effective)
        source_hits(ev, scoped, effective, {"docs/a", "docs/sub/b"})
    for raw_source, code in (("", "invalid_source"), ([], "invalid_source"), ({"source": "alpha"}, "invalid_source"),
                             ("beta", "source_not_allowed"), ("missing", "source_not_found")):
        args = {"query": "needle", "source_id": raw_source}
        old, scoped = send([request(args), request({**args, "uri": "private-uri-marker"})])
        value = payload(ev, old, error=True)
        ev.need(old["result"] == scoped["result"] and value["error"]["code"] == code and value["error"]["field"] == "source_id", "paired source errors precede string URI parsing")
    precedence = send([request({"query": "", "source_id": "beta", "uri": "private-uri-marker"}),
                       request({"query": "", "source_id": "beta", "uri": None})])
    ev.need(precedence[0]["result"]["isError"] and precedence[0]["result"]["content"][0]["text"] == "query required", "legacy query-error precedence for URI strings")
    uri_error(ev, precedence[1])
    prefix = b'{"jsonrpc":"2.0","id":49,"method":"tools/call","params":{"name":"search","arguments":{"query":"needle","uri":"'
    bad_wire = [b"{", prefix + b'\\ud800"}}}', prefix + b'\\uZZZZ"}}}', prefix + b'\xff"}}}', prefix + b'\x00"}}}']
    for response in send(bad_wire):
        ev.need(response.get("id") is None and response.get("error", {}).get("code") == -32700 and "result" not in response, "malformed JSON/UTF8/escape/raw NUL stays parse error before dispatch")
    denied = send([request({"action": "capture", "payload": "{}"}, "memory_write")])[0]
    ev.need(denied.get("result", {}).get("isError") is True and "write_denied" in json.dumps(denied), "default-deny MCP writes preserved")
    # Rejecting malformed input does not poison the next request on the actual transport.
    recovery = send([request({"query": "needle", "source_id": "alpha", "uri": uri, "no_vector": True})])[0]
    source_hits(ev, recovery, "alpha", {"docs/a", "docs/sub/b"})


def ambient(f: Fixture, profile: str, send, actual_source: str) -> None:
    ev = f.ev
    for null_source in (False, True):
        args = {"query": "needle", "no_vector": True, "limit": 20}
        if null_source:
            args["source_id"] = None
        old, scoped = send([request(args), request({**args, "uri": f"qbrain://{actual_source or 'default'}/resources/docs/"})])
        if actual_source:
            source_hits(ev, old, actual_source)
            source_hits(ev, scoped, actual_source, {"docs/a", "docs/sub/b"})
        else:
            value = payload(ev, old, error=True)
            ev.need(old["result"] == scoped["result"] and value["error"]["code"] == "invalid_source", "present-empty ambient source remains invalid with omitted/null explicit source")
        override = send([request({**args, "source_id": "default", "uri": "qbrain://default/resources/docs/"})])[0]
        source_hits(ev, override, "default", {"docs/a", "docs/sub/b"})



class EmbeddingProvider:
    """Ordinary, isolated loopback HTTP fixture; captures exact request/response bytes."""
    MODEL = "n49d-fixture-model"
    KEY = "n49d-synthetic-embedding-key"
    REQUEST_LIMIT = 32768
    MAX_REQUESTS = 128

    def __init__(self, ev: Evidence):
        self.ev = ev
        self.records: list[dict] = []
        self.errors: list[str] = []
        self.condition = threading.Condition()
        self.active = False
        owner = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                request_bytes = bytearray()
                response_bytes = b""
                record = {"status": "receiving"}
                deadline = time.monotonic() + 5
                with owner.condition:
                    owner.active = True
                    owner.records.append(record)
                    over_count = len(owner.records) > owner.MAX_REQUESTS
                try:
                    if over_count:
                        raise ValueError("provider request count budget exceeded")
                    while b"\r\n\r\n" not in request_bytes:
                        self.request.settimeout(max(0.001, deadline - time.monotonic()))
                        if time.monotonic() >= deadline:
                            raise TimeoutError("provider request deadline")
                        chunk = self.request.recv(4096)
                        if not chunk:
                            raise ValueError("incomplete provider headers")
                        request_bytes.extend(chunk)
                        if len(request_bytes) > owner.REQUEST_LIMIT:
                            raise ValueError("provider request byte budget exceeded")
                    header, body = bytes(request_bytes).split(b"\r\n\r\n", 1)
                    lines = header.split(b"\r\n")
                    if lines[0] != b"POST /v1/embeddings HTTP/1.1":
                        raise ValueError("unexpected embedding provider endpoint")
                    headers = {}
                    for line in lines[1:]:
                        key, value = line.split(b":", 1)
                        key = key.lower()
                        if key in headers:
                            raise ValueError("duplicate provider request header")
                        headers[key] = value.strip()
                    length = int(headers[b"content-length"])
                    if not 0 < length <= owner.REQUEST_LIMIT - len(header) - 4:
                        raise ValueError("provider content length budget")
                    while len(body) < length:
                        self.request.settimeout(max(0.001, deadline - time.monotonic()))
                        if time.monotonic() >= deadline:
                            raise TimeoutError("provider request deadline")
                        chunk = self.request.recv(min(4096, length - len(body)))
                        if not chunk:
                            raise ValueError("incomplete provider request body")
                        request_bytes.extend(chunk)
                        body += chunk
                    if len(body) != length:
                        raise ValueError("provider request framing mismatch")
                    value = json.loads(body)
                    if headers.get(b"authorization") != b"Bearer " + owner.KEY.encode("ascii"):
                        raise ValueError("synthetic provider authorization missing")
                    if (value.get("model") != owner.MODEL or value.get("dimensions") != 3
                            or value.get("encoding_format") != "float"
                            or not isinstance(value.get("input"), list) or len(value["input"]) != 1
                            or not isinstance(value["input"][0], str)):
                        raise ValueError("embedding request contract mismatch")
                    record["query"] = value["input"][0]
                    body_out = wire({"model": owner.MODEL, "data": [{"index": 0, "embedding": [1.0, 1.0, 1.0]}]})
                    response_bytes = (b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                                      + str(len(body_out)).encode("ascii")
                                      + b"\r\nConnection: close\r\n\r\n" + body_out)
                    self.request.settimeout(max(0.001, deadline - time.monotonic()))
                    self.request.sendall(response_bytes)
                    record["status"] = "completed"
                except BaseException as error:
                    record.update(status="failed", failure=type(error).__name__ + ": " + str(error))
                    with owner.condition:
                        owner.errors.append(record["failure"])
                finally:
                    try:
                        record["request"] = ev.blob(ev.path("provider-request.bin"), bytes(request_bytes))
                        record["response"] = ev.blob(ev.path("provider-response.bin"), response_bytes)
                    except BaseException as error:
                        record.update(status="failed", failure="provider raw evidence failure: " + str(error))
                        with owner.condition:
                            owner.errors.append(record["failure"])
                    with owner.condition:
                        owner.active = False
                        owner.condition.notify_all()

        self.server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.02}, daemon=True)
        self.thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}/v1"

    def snapshot(self) -> list[dict]:
        with self.condition:
            finished = self.condition.wait_for(lambda: not self.active, timeout=6)
            if not finished:
                raise TimeoutError("provider request finalization deadline")
            if self.errors:
                raise ValueError("loopback provider fixture failed: " + self.errors[0])
            return [dict(record) for record in self.records]

    def close(self) -> None:
        # A handler has one five-second absolute request deadline. Shutdown and
        # thread join must complete before a successful evidence report.
        shutdown = threading.Thread(target=self.server.shutdown, daemon=True)
        shutdown.start()
        shutdown.join(timeout=6)
        self.thread.join(timeout=1)
        self.server.server_close()
        self.ev.need(not shutdown.is_alive() and not self.thread.is_alive(), "owned embedding provider thread terminates")
        self.snapshot()


def provider_validation(ev: Evidence, binary: Path, root: Path, report: dict) -> None:
    """Windows-only external observation, without production/cache instrumentation."""
    ev.need(os.name == "nt", "provider HTTP proof requires the native Windows client")
    root.mkdir()
    f = Fixture(ev, binary, root)
    f.seed()
    provider = EmbeddingProvider(ev)
    report.update(status="running", profiles=["full", "memory"], transports=["stdio", "http"],
                  batches=[], requests=provider.records)
    try:
        f.env["QBRAIN_EMBED_MOCK"] = "0"
        for key, value in (("embedding.base_url", provider.base_url), ("embedding.model", provider.MODEL),
                           ("embedding.api_key", provider.KEY), ("embedding.dimensions", "3")):
            f.sql("INSERT INTO config(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
        f.sql("UPDATE content_chunks SET embedding=?,dim=3,model=?", (struct.pack("<fff", 1, 1, 1), provider.MODEL))
        baseline = f.snapshot()
        uri = "qbrain://alpha/resources/docs/"
        query_serial = 0

        def unique(label: str) -> str:
            nonlocal query_serial
            query_serial += 1
            return f"n49dprovider{query_serial:04d}{label}unique"

        for profile in ("full", "memory"):
            for transport in ("stdio", "http"):
                server = Http(f, profile) if transport == "http" else None
                batch = {"profile": profile, "transport": transport, "status": "running",
                         "negative_cases": [], "positive_controls": []}
                report["batches"].append(batch)
                success = False
                try:
                    def send(raw: bytes) -> dict:
                        return server.exchange(raw) if server else f.stdio(profile, [raw])[0]

                    def positive(label: str) -> None:
                        query = unique("positive" + label)
                        before = len(provider.snapshot())
                        response = send(request({"query": query, "source_id": "alpha", "uri": uri, "limit": 20}))
                        source_hits(ev, response, "alpha", {"docs/a", "docs/sub/b"})
                        records = provider.snapshot()
                        ev.need(len(records) == before + 1 and records[-1].get("query") == query
                                and records[-1]["status"] == "completed", "fresh valid query reaches the same ordinary loopback embedding provider")
                        batch["positive_controls"].append({"query": query, "provider_requests": 1, "record_index": before})

                    positive("before")
                    invalid = []
                    for value in (None, True, 7, [], {"private": "value"}, "", "private-uri-marker",
                                  "qbrain://alpha/resources/docs", "qbrain://alpha/resources/../",
                                  "qbrain://alpha/resources/a%2fb/", "qbrain://alpha/resources/a%5cb/",
                                  "qbrain://alpha/resources/a\\b/", "qbrain://alpha/resources//",
                                  "qbrain://ALPHA/resources/docs/", "qbrain://beta/resources/docs/",
                                  "qbrain://missing/resources/docs/", "qbrain://alpha/unknown/docs/",
                                  "qbrain://alpha/resources/a\0b/", "qbrain://alpha/resources/" + "x" * 9000 + "/"):
                        query = unique("uri")
                        invalid.append((query, request({"query": query, "source_id": "alpha", "uri": value}), "uri"))
                    for source, code in (("beta", "source_not_allowed"), ("missing", "source_not_found"), ("", "invalid_source"), ([], "invalid_source")):
                        query = unique("source")
                        invalid.append((query, request({"query": query, "source_id": source, "uri": uri}), code))
                    for invalid_bytes in (b'\\ud800', b'\\uZZZZ', b'\xff', b'\x00'):
                        query = unique("wire")
                        prefix = b'{"jsonrpc":"2.0","id":49,"method":"tools/call","params":{"name":"search","arguments":{"query":' + wire(query) + b',"source_id":"alpha","uri":"'
                        invalid.append((query, prefix + invalid_bytes + b'"}}}', "parse"))
                    for query, raw, expected in invalid:
                        before = len(provider.snapshot())
                        response = send(raw)
                        after = len(provider.snapshot())
                        case = {"query": query, "expected_error": expected, "provider_requests": after - before}
                        batch["negative_cases"].append(case)
                        ev.need(after == before, "unique invalid URI/source/wire query makes zero provider requests")
                        if expected == "uri":
                            uri_error(ev, response)
                        elif expected == "parse":
                            ev.need(response.get("id") is None and response.get("error", {}).get("code") == -32700
                                    and "result" not in response, "provider-negative malformed wire remains parse error")
                        else:
                            value = payload(ev, response, error=True)
                            ev.need(value["error"]["code"] == expected and value["error"]["field"] == "source_id", "provider-negative source authorization/existence error preserved")
                    positive("after")
                    batch.update(status="passed", negative_request_count=0, negative_query_count=len(invalid))
                    success = True
                finally:
                    if server:
                        server.close(success)
        records = provider.snapshot()
        positive_queries = [case["query"] for batch in report["batches"] for case in batch["positive_controls"]]
        rejected_queries = {case["query"] for batch in report["batches"] for case in batch["negative_cases"]}
        ev.need(len(records) == 8 and [record.get("query") for record in records] == positive_queries,
                "provider capture contains exactly eight fresh valid controls across both profiles/transports")
        ev.need(not rejected_queries.intersection(record.get("query") for record in records), "no unique rejected query appears in complete provider request capture")
        ev.need(f.snapshot() == baseline, "provider observation stage leaves synthetic application rows unchanged")
        report.update(status="passed", positive_request_count=len(records), negative_request_count=0,
                      negative_query_count=len(rejected_queries))
    except BaseException:
        report["status"] = "failed"
        raise
    finally:
        try:
            provider.close()
        except BaseException:
            report["status"] = "failed"
            raise

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    ev = Evidence(args.output.resolve())
    before_hash = sha(binary.read_bytes())
    report = {"schema": "qbrain-n49d-mcp-directory-process-v1", "base_contract_commit": BASE_COMMIT,
              "platform": platform.platform(), "python_optimized": not __debug__, "binary_sha256": before_hash,
              "passed": False, "status": "running", "paid_requests": 0, "postgres_executed": False,
              "expected_full_tool_count": 112, "expected_memory_tool_count": 6,
              "provider_http": {"required": os.name == "nt", "status": "pending" if os.name == "nt" else "not_applicable",
                                "reason": "ordinary native Windows loopback embedding-provider observation" if os.name == "nt" else "Linux has functional built-in mock-vector coverage only; no provider-network/count claim"},
              "http": {"required": os.name == "nt", "status": "pending" if os.name == "nt" else "not_applicable",
                       "reason": "native Windows transport required" if os.name == "nt" else "non-Windows production HTTP server is a stub; no actual HTTP PASS claimed"}}
    try:
        with tempfile.TemporaryDirectory(prefix="qbrain-n49d-") as temp:
            root = Path(temp) / "fixture"; root.mkdir()
            f = Fixture(ev, binary, root)
            f.seed()
            initial = f.snapshot()
            definitions = {
                "default": ("needle", "qbrain://default/resources/docs/", False, "balanced"),
                "alpha": ("needle", "qbrain://alpha/resources/docs/", False, "balanced"),
                "root": ("needle", "qbrain://alpha/resources/", False, "balanced"),
                "skills": ("needle", "qbrain://alpha/skills/docs/", False, "balanced"),
                "memories": ("needle", "qbrain://alpha/memories/docs/", False, "balanced"),
                "unicode": ("针", "qbrain://alpha/resources/文档/", False, "balanced"),
                "vector": ("vectoronlyquery", "qbrain://alpha/resources/docs/", True, "balanced"),
                "no_vector": ("vectoronlyquery", "qbrain://alpha/resources/docs/", False, "balanced"),
                "conservative": ("vectoronlyquery", "qbrain://alpha/resources/docs/", True, "conservative"),
                "empty": ("needle", "qbrain://alpha/resources/absent/", False, "balanced"),
            }
            cli = {label: f.cli(*definition) for label, definition in definitions.items()}
            legacy_cli = f.cli("needle", None)
            ev.need(bool(legacy_cli) and any(hit["source_id"] != "alpha" for hit in legacy_cli), "no-URI local CLI remains cross-source; no false CLI/MCP legacy-equivalence claim")
            for profile in ("full", "memory"):
                exercise(f, profile, "stdio", cli)
                for source in ("alpha", ""):
                    ambient(f, profile, lambda messages, source=source: f.stdio(profile, messages, {"QBRAIN_SOURCE": source}), source)
            report["stdio"] = {"status": "passed", "profiles": ["full", "memory"]}
            if os.name == "nt":
                for profile in ("full", "memory"):
                    server = Http(f, profile)
                    ok = False
                    try:
                        ping = wire({"jsonrpc": "2.0", "id": 1, "method": "ping"})
                        server.exchange(ping, token=None, expected=401)
                        server.exchange(ping, token="wrong-synthetic-token", expected=401)
                        exercise(f, profile, "http", cli, server)
                        ok = True
                    finally:
                        server.close(ok)
                    for source in ("alpha", ""):
                        server = Http(f, profile, {"QBRAIN_SOURCE": source})
                        ok = False
                        try:
                            ambient(f, profile, lambda messages: [server.exchange(message) for message in messages], source)
                            ok = True
                        finally:
                            server.close(ok)
                report["http"].update(status="passed", profiles=["full", "memory"], authentication="missing/wrong token rejected; synthetic bearer accepted")
            ev.need(f.snapshot() == initial, "CLI/MCP retrieval rejection and default-deny writes leave application rows unchanged")
            if os.name == "nt":
                provider_validation(ev, binary, Path(temp) / "provider-fixture", report["provider_http"])
            ev.need(sha(binary.read_bytes()) == before_hash, "candidate executable identity stable before/after actual process checks")
            report.update(passed=True, status="passed")
    except BaseException as error:
        report.update(status="failed", failure=type(error).__name__ + ": " + str(error), traceback=traceback.format_exc())
    finally:
        cleanup_errors = []
        for child in ev.children:
            if not child.closed:
                try:
                    child.stop("cleanup_after_failure")
                except BaseException as error:
                    cleanup_errors.append(str(error))
        if cleanup_errors:
            report.update(passed=False, status="failed", cleanup_errors=cleanup_errors)
        report.update(checks=ev.checks, check_count=len(ev.checks), commands=ev.commands,
                      command_count=len(ev.commands), exchanges=ev.exchanges, exchange_count=len(ev.exchanges))
        (ev.output / "RESULT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: report[key] for key in ("schema", "passed", "status", "check_count", "command_count", "exchange_count", "http")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
