"""Strict acceptance of fixed native HTTP cancellation schedules; no provider data."""
from __future__ import annotations
import re

VARIANTS = ("legacy", "pooled", "current", "current_repeat")
ROUNDS, REQUESTS, GROWTH = 8, 32, 16


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, name):
    require(type(value) is int and value >= 0, "Invalid nonnegative integer: " + name)
    return value


def validate_report(report, *, source_commit, probe_hashes, require_pass=True):
    require(isinstance(report, dict), "Missing lifecycle report")
    require(report.get("result") == ("PASS" if require_pass else "FAIL"),
            "Unexpected lifecycle report status")
    require(report.get("native_windows") is True, "Native Windows evidence required")
    require(isinstance(source_commit, str) and re.fullmatch(r"[0-9a-f]{40}", source_commit),
            "Invalid expected source")
    require(report.get("source_commit") == source_commit, "Wrong lifecycle source")
    require(report.get("pool_policy") == "session_private", "Wrong current pool policy")
    require(report.get("rounds_per_variant") == ROUNDS and
            type(report.get("rounds_per_variant")) is int, "Incomplete round schedule")
    require(report.get("requests_per_round") == REQUESTS and
            type(report.get("requests_per_round")) is int, "Wrong request schedule")
    require(report.get("allowed_growth") == GROWTH and
            type(report.get("allowed_growth")) is int, "Changed handle ceiling")
    variants = report.get("variants")
    require(isinstance(variants, dict) and set(variants) == set(VARIANTS),
            "Missing or extra lifecycle variant")
    require(set(probe_hashes) == {"legacy", "pooled", "current"}, "Incomplete expected hashes")
    for name in VARIANTS:
        variant = variants[name]
        require(isinstance(variant, dict), "Invalid variant")
        expected_hash = probe_hashes["current" if name == "current_repeat" else name]
        require(isinstance(expected_hash, str) and re.fullmatch(r"[0-9a-f]{64}", expected_hash),
                "Invalid expected probe hash")
        require(variant.get("sha256") == expected_hash, "Wrong probe binary")
        require(type(variant.get("exit_code")) is int and variant["exit_code"] == 0,
                "Probe did not exit successfully")
        rows = variant.get("samples")
        require(isinstance(rows, list) and len(rows) == ROUNDS, "Incomplete lifecycle samples")
        for n, row in enumerate(rows, 1):
            require(isinstance(row, dict), "Invalid lifecycle sample")
            for key in ("timeout_count", "requested", "opened", "closed", "close_errors",
                        "states_created", "states_destroyed", "final_callbacks",
                        "callbacks_without_parents", "handles_at_250ms", "handles_at_2000ms"):
                integer(row.get(key), key)
            require(row["timeout_count"] == row["requested"] == REQUESTS,
                    "Not every request timed out without a partial response")
            require(row["opened"] == row["closed"] == n * REQUESTS * 3 and
                    row["close_errors"] == 0, "Owned HTTP handles not balanced")
            require(row["states_created"] == row["states_destroyed"] ==
                    row["final_callbacks"] == n * REQUESTS, "Async state/callbacks not balanced")
            require(row["callbacks_without_parents"] == (n * REQUESTS if name == "legacy" else 0),
                    "Parent lifetime policy mismatch")
            require(row["handles_at_250ms"] > 0 and row["handles_at_2000ms"] > 0,
                    "Missing process handle observation")
        # Controls measure the old behaviors and must not be treated as fixed code.
        # Neither current run can substitute for a failure of the other.
        if name.startswith("current"):
            require(max(r["handles_at_2000ms"] for r in rows[1:]) <=
                    rows[0]["handles_at_2000ms"] + GROWTH,
                    "Process handles grew beyond the unchanged ceiling: " + name)
    return {"variants": len(VARIANTS), "requests_per_variant": ROUNDS * REQUESTS,
            "current_requests": 2 * ROUNDS * REQUESTS}
