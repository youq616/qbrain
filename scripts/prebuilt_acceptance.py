"""Offline, pinned Qbrain preview preparation; Python is an acceptance tool only.

No downloads, compiler installation, persistent environment edits or Agent launches.
The archive hash is the trust anchor, not a manifest supplied by an arbitrary ZIP.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import uuid
import zipfile

PIN = {
    "source_commit": "464045e2451ec71ca37dd8e92bcf4ac0d9325a0b",
    "archive_sha256": "4f43e91853602bd141822ad11650ddab9643a3471f8a86bd2c615ffb61c460ee",
    "binary_sha256": "0fae586ddb6d2d12a539c94d87d5a6532da42682e34e3e8d039af140f8058d7c",
}
MAX_BYTES = 64 * 1024 * 1024
MAX_FILES = 128
REQUIRED = {"qbrain.exe", "scripts/Install-QbrainMemory.ps1",
            "scripts/Invoke-QbrainJson.ps1", "verification/validation.json"}


class AcceptanceError(ValueError):
    """An input or native result did not satisfy the acceptance contract."""


def require(value: bool, message: str) -> None:
    if not value:
        raise AcceptanceError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def load_json(data: bytes) -> dict:
    value = json.loads(data.decode("utf-8-sig"), object_pairs_hook=unique_object)
    require(isinstance(value, dict), "Expected JSON object")
    return value


def safe_member(name: str) -> None:
    # Apply Windows rules even when reviewing on Linux. The delivered package
    # needs only ASCII names, not device paths, drive prefixes or NTFS streams.
    require(bool(re.fullmatch(r"[A-Za-z0-9_./-]+", name)), "Unsafe archive path")
    parts = name.split("/")
    reserved = {"con", "prn", "aux", "nul"} | {
        f"{prefix}{i}" for prefix in ("com", "lpt") for i in range(1, 10)}
    for part in parts:
        require(part not in ("", ".", "..") and not part.endswith("."),
                "Unsafe archive component")
        require(part.split(".")[0].lower() not in reserved, "Windows device name")


def verify_bytes(raw: bytes, pin: dict = PIN) -> dict[str, bytes]:
    require(len(raw) <= MAX_BYTES, "Archive exceeds byte cap")
    require(digest(raw) == pin["archive_sha256"], "Archive SHA-256 mismatch; do not execute")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        require(0 < len(infos) <= MAX_FILES, "Invalid archive member count")
        names: set[str] = set()
        total = 0
        for info in infos:
            safe_member(info.filename)
            folded = info.filename.lower()
            require(folded not in names, "Duplicate or case-colliding archive member")
            names.add(folded)
            mode = info.external_attr >> 16
            require(stat.S_IFMT(mode) in (0, stat.S_IFREG), "Non-regular ZIP member")
            require(not (info.flag_bits & 1), "Encrypted ZIP member")
            require(0 <= info.file_size <= MAX_BYTES, "ZIP member exceeds byte cap")
            total += info.file_size
            require(total <= MAX_BYTES, "Unpacked archive exceeds byte cap")
        payloads = {info.filename: archive.read(info) for info in infos}
    # No writes occur until all members, CRCs, manifests and hashes pass.
    require("MANIFEST.json" in payloads, "Missing manifest")
    manifest = load_json(payloads["MANIFEST.json"])
    require(manifest.get("source_commit") == pin["source_commit"], "Wrong source commit")
    require(manifest.get("result") == "PASS", "Original package lacks passing validation")
    inventory = manifest.get("files")
    require(isinstance(inventory, dict) and REQUIRED <= inventory.keys(), "Incomplete inventory")
    require(set(payloads) == set(inventory) | {"MANIFEST.json", "README-FIRST.txt"},
            "Unlisted or missing package member")
    for name, metadata in inventory.items():
        require(isinstance(metadata, dict), "Invalid member metadata")
        require(type(metadata.get("bytes")) is int and metadata["bytes"] == len(payloads[name]),
                "Manifest byte count mismatch")
        require(metadata.get("sha256") == digest(payloads[name]), "Manifest member hash mismatch")
    binary_hash = digest(payloads["qbrain.exe"])
    require(binary_hash == pin["binary_sha256"] == manifest.get("binary_sha256"),
            "Executable SHA-256 mismatch")
    validation = load_json(payloads["verification/validation.json"])
    require(validation.get("source_commit") == pin["source_commit"] and
            validation.get("binary_sha256") == binary_hash and validation.get("result") == "PASS",
            "Validation provenance mismatch")
    return payloads


def no_reparse_parents(path: Path) -> None:
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode) and not (
            getattr(info, "st_file_attributes", 0) & 0x400), "Reparse/symlink output path")


def isolated_environment(root: Path, original: dict[str, str]) -> dict[str, str]:
    env = {k: v for k, v in original.items() if not k.upper().startswith(
        ("QBRAIN", "OPENAI", "ANTHROPIC")) and k.upper() not in
        {"HOME", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "TEMP", "TMP"}}
    env.update({key: str(root) for key in
                ("HOME", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "TEMP", "TMP")})
    # Defense in depth: the smoke uses only local extraction and lexical reads.
    env["QBRAIN_EMBED_MOCK"] = "1"
    return env


def run_smoke(binary: Path, output: Path) -> tuple[list[dict], bool]:
    """Native CLI memory test, not a live Agent, Hook or paid-model acceptance."""
    if os.name != "nt":
        return [{"name": "native_cli_memory", "status": "BLOCKED",
                 "reason": "Native Windows execution required"}], False
    home = output / "smoke-data"
    home.mkdir()
    env = isolated_environment(home, dict(os.environ))
    logs = output / "logs"
    logs.mkdir()
    records = []

    def invoke(arguments: list[str], payload: object = None) -> dict:
        number = len(records) + 1
        encoded = b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            result = subprocess.run([str(binary), *arguments], input=encoded,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    cwd=home, env=env, timeout=30, check=False)
        except subprocess.TimeoutExpired as error:
            records.append({"name": f"cli_{number}", "status": "FAIL", "reason": "timeout"})
            raise AcceptanceError("Native command exceeded 30 seconds") from error
        (logs / f"cli-{number}.stdout.log").write_bytes(result.stdout)
        (logs / f"cli-{number}.stderr.log").write_bytes(result.stderr)
        records.append({"name": f"cli_{number}", "arguments": arguments,
                        "status": "PASS" if result.returncode == 0 else "FAIL",
                        "exit_code": result.returncode})
        require(result.returncode == 0, f"Native command {number} failed; see isolated logs")
        if arguments[0] == "init":
            return {}
        return load_json(result.stdout)

    try:
        marker = "QBLOCAL" + uuid.uuid4().hex
        quote = "I prefer the test log prefix " + marker + "."
        invoke(["init", "--brain", "prebuilt-a", "--no-default"])
        event = invoke(["memory", "capture", "--brain", "prebuilt-a", "--manual"],
                       {"session_id": "acceptance-one", "fragment_id": "fragment-one",
                        "messages": [{"role": "user", "content": quote}]})
        require(event.get("status") == "archived" and isinstance(event.get("event_id"), str),
                "Manual memory capture did not archive")
        invoke(["memory", "extract", "--brain", "prebuilt-a", "--event", event["event_id"]])
        found = invoke(["memory", "read", "--brain", "prebuilt-a", "--query", marker])
        require(any(x.get("quote") == quote for x in found.get("items", [])), "Exact quote not recalled")
        invoke(["init", "--brain", "prebuilt-b", "--no-default"])
        other = invoke(["memory", "read", "--brain", "prebuilt-b", "--query", marker])
        require(other.get("items") == [], "Separate brain returned the test memory")
        records.append({"name": "native_cli_memory", "status": "PASS",
                        "scope": "separate-process exact quote and separate-brain isolation"})
        return records, True
    except (AcceptanceError, OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        records.append({"name": "native_cli_memory", "status": "FAIL",
                        "error_type": type(error).__name__})
        return records, False


def summarize(checks: list[dict]) -> dict:
    states = {"PASS", "FAIL", "SKIP", "BLOCKED", "NOT_RUN"}
    require(all(item.get("status") in states for item in checks), "Invalid result state")
    counts = Counter(item["status"] for item in checks)
    return {"total": len(checks), **{state: counts[state] for state in sorted(states)}}


def prepare(package: Path, output: Path | None, smoke: bool) -> tuple[Path, dict]:
    # Read exactly the bytes that are hashed; no verify-then-reopen archive race.
    with package.open("rb") as stream:
        payloads = verify_bytes(stream.read(MAX_BYTES + 1))
    if output is None:
        output = Path(tempfile.gettempdir()) / ("QbrainAcceptance-" + uuid.uuid4().hex)
    output = Path(os.path.abspath(output))
    no_reparse_parents(output)
    require(not output.exists(), "Output already exists; use a new directory")
    output.mkdir(parents=True, exist_ok=False)
    staged = output / "package"
    staged.mkdir()
    for name, contents in payloads.items():
        target = staged / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(contents)
    checks = [{"name": "pinned_package_integrity", "status": "PASS", "files": len(payloads)}]
    if smoke:
        rows, _ = run_smoke(staged / "qbrain.exe", output)
        checks.extend(rows)
    else:
        checks.append({"name": "native_cli_memory", "status": "NOT_RUN"})
    checks.extend([
        {"name": "local_source_build", "status": "NOT_RUN", "reason": "Prebuilt mode; not required"},
        {"name": "full_native_regression", "status": "NOT_RUN", "reason": "Historical CI evidence only"},
        {"name": "real_agent_lifecycle", "status": "NOT_RUN", "reason": "Requires actual client sessions"},
    ])
    status = "FAIL" if any(r["status"] == "FAIL" for r in checks) else (
        "BLOCKED" if any(r["status"] == "BLOCKED" for r in checks) else "PASS")
    report = {"mode": "prebuilt_acceptance", "result": status,
              "result_scope": "Only requested preparation/CLI smoke; not full acceptance",
              "repository": "youq616/qbrain", **PIN, "platform": sys.platform,
              "package_dir": str(staged), "checks": checks, "counts": summarize(checks),
              "real_agent_verified": False, "signed_release_claimed": False}
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return output, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True, help="Original inner N46D queue-fix ZIP")
    parser.add_argument("--output", type=Path, help="New directory only; default unique temporary directory")
    parser.add_argument("--run-smoke", action="store_true", help="Execute isolated native CLI memory check")
    args = parser.parse_args()
    try:
        output, report = prepare(args.package, args.output, args.run_smoke)
        print(json.dumps({"result": report["result"], "summary": str(output / "summary.json"),
                          "package_dir": report["package_dir"], "counts": report["counts"]}))
        return 0 if report["result"] == "PASS" else 2
    except (AcceptanceError, OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        # Do not echo untrusted archive content, credentials or parser excerpts.
        print(json.dumps({"result": "FAIL", "stage": "preparation",
                          "error_type": type(error).__name__,
                          "message": str(error) if isinstance(error, AcceptanceError)
                                     else "Cannot read or validate package/output"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
