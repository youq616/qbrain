"""Validate fixed native cancellation schedules and explicit shared-session release."""
from __future__ import annotations
import re

VARIANTS = ("legacy", "per_call", "current", "current_repeat")
ROUNDS, REQUESTS, GROWTH = 8, 32, 16
FIELDS = ("timeout_count", "requested", "opened", "closed", "close_errors",
          "states_created", "states_destroyed", "final_callbacks",
          "callbacks_without_parents", "handles_at_250ms", "handles_at_2000ms")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, name):
    require(type(value) is int and value >= 0, "Invalid nonnegative integer: " + name)
    return value


def sample(row, name, requests, *, shutdown=False):
    require(isinstance(row, dict), "Invalid lifecycle sample")
    for key in FIELDS:
        integer(row.get(key), key)
    require(row.get("cache_released") is shutdown, "Wrong session release state")
    require(row["timeout_count"] == row["requested"] == (0 if shutdown else REQUESTS),
            "Not every request timed out without a partial response")
    shared = name.startswith("current")
    opened = requests * (2 if shared else 3) + int(shared)
    outstanding = int(shared and not shutdown)
    require(row["opened"] == opened and row["closed"] == opened - outstanding and
            row["close_errors"] == 0, "Owned HTTP handles not balanced against explicit session lifetime")
    require(row["states_created"] == row["states_destroyed"] ==
            row["final_callbacks"] == requests, "Async state/callbacks not balanced")
    require(row["callbacks_without_parents"] == (requests if name == "legacy" else 0),
            "Parent lifetime policy mismatch")
    require(row["handles_at_250ms"] > 0 and row["handles_at_2000ms"] > 0,
            "Missing process handle observation")


def validate_report(report, *, source_commit, probe_hashes, require_pass=True):
    require(isinstance(report, dict), "Missing lifecycle report")
    require(report.get("result") == ("PASS" if require_pass else "FAIL"), "Unexpected lifecycle status")
    require(report.get("native_windows") is True, "Native Windows evidence required")
    require(isinstance(source_commit, str) and re.fullmatch(r"[0-9a-f]{40}", source_commit),
            "Invalid expected source")
    require(report.get("source_commit") == source_commit, "Wrong lifecycle source")
    require(report.get("session_policy") == "shared_immutable_request_timeouts", "Wrong session policy")
    for key, expected in (("rounds_per_variant", ROUNDS), ("requests_per_round", REQUESTS),
                          ("allowed_growth", GROWTH)):
        require(type(report.get(key)) is int and report[key] == expected, "Changed fixed schedule: " + key)
    variants = report.get("variants")
    require(isinstance(variants, dict) and set(variants) == set(VARIANTS), "Missing/extra variant")
    require(set(probe_hashes) == {"legacy", "per_call", "current"}, "Incomplete expected probe hashes")
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
            sample(row, name, n * REQUESTS)
        final = variant.get("shutdown")
        sample(final, name, ROUNDS * REQUESTS, shutdown=True)
        # A deliberately retained singleton is counted while running and must
        # close on explicit diagnostic shutdown, rather than being hidden as zero.
        # All process-count limits still use the original +16 and fixed times.
        if name.startswith("current"):
            require(max(r["handles_at_2000ms"] for r in rows[1:] + [final]) <=
                    rows[0]["handles_at_2000ms"] + GROWTH,
                    "Process handles grew beyond the unchanged ceiling: " + name)
    return {"variants": len(VARIANTS), "requests_per_variant": ROUNDS * REQUESTS,
            "current_requests": 2 * ROUNDS * REQUESTS, "shutdown_verified": True}
