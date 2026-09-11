"""One-time source-only patch application. No model calls or user databases."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "0e24492f39cae4a04163eccc50ff9e3684d2a751384e4df187afa9b2b5129c7d"
MARKER = ROOT / ".ci/n42.applied.json"


def target(name: str) -> Path:
    path = ROOT / name
    if not path.resolve().is_relative_to(ROOT) or path.is_symlink():
        raise ValueError(f"Unsafe patch path: {name}")
    if Path(name).parts[0] not in {"include", "src", "tests", "scripts", "CMakeLists.txt"}:
        raise ValueError(f"Unexpected patch target: {name}")
    return path


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def main() -> None:
    if MARKER.exists():
        print("N42 already applied; source files are not overwritten.")
        return
    encoded = "".join((ROOT / f".ci/n42/part-{i:02d}.b64").read_text(encoding="ascii").strip() for i in range(4))
    compressed = base64.b64decode(encoded, validate=True)
    decoder = zlib.decompressobj()
    raw = decoder.decompress(compressed, 1_000_000)
    if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError("Invalid or oversized compressed payload")
    if hashlib.sha256(raw).hexdigest() != EXPECTED:
        raise ValueError("N42 payload SHA-256 mismatch")
    payload = json.loads(raw)
    pending: dict[Path, bytes] = {}
    for change in payload["changes"]:
        path = target(change["path"])
        before = path.read_bytes()
        if blob_sha(before) != change["base_blob_sha"]:
            raise ValueError(f"Base file hash mismatch: {change['path']}")
        text = before.decode("utf-8")
        for edit in change["edits"]:
            if text.count(edit["old"]) != edit["count"]:
                raise ValueError(f"Ambiguous replacement: {change['path']}")
            text = text.replace(edit["old"], edit["new"])
        pending[path] = text.encode("utf-8")
    for name, content in payload["new_files"].items():
        path = target(name)
        if path.exists() or path in pending:
            raise ValueError(f"New path already exists: {name}")
        pending[path] = content.encode("utf-8")
    # Every preimage and replacement is validated before the first write.
    for path, data in pending.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"Applied: {path.relative_to(ROOT).as_posix()}")
    report = {
        "upstream_commit": payload["base_commit"],
        "payload_sha256": EXPECTED,
        "changed_files": {p.relative_to(ROOT).as_posix(): hashlib.sha256(b).hexdigest() for p, b in pending.items()},
        "acceptance": "development patch; native build, regression and transport acceptance tracked separately",
    }
    MARKER.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (ROOT / ".ci/n42/edits.json").write_text(json.dumps({k: v for k, v in payload.items() if k != "new_files"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Remove the superseded transport staging file; the verified chunks remain.
    (ROOT / ".ci/n42-payload.b64").unlink(missing_ok=True)
    print(f"Verified payload and applied {len(pending)} source/test files.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"N42 application refused: {exc}", file=sys.stderr)
        raise SystemExit(1)
