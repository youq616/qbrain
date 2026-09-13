"""Independent evidence gate; these counts are not product capabilities."""
EXPECTED_CHECKS = frozenset(['unextracted_archive_not_memory', 'memory_single_char', 'memory_double_char', 'memory_mixed_ascii', 'memory_noncontiguous_miss', 'mcp_memory_read_hit', 'search_phrase_hits', 'search_single_char_hits', 'search_ext_block_hits', 'search_kana_hits', 'search_hangul_hits', 'append_beside_fts', 'dedupe_by_page', 'mcp_put_alpha_ok', 'source_filter_alpha', 'source_denied', 'like_special_literal', 'sql_style_literal', 'db_alive_after_sql', 'title_match', 'slug_match', 'ascii_fts_still_works', 'ascii_no_supplement_noise', 'stable_order', 'search_limit', 'memory_limit_and_bytes', 'update_visible', 'update_old_gone', 'soft_delete_excluded', 'hard_delete_excluded', 'memory_forget', 'expired_memory_excluded', 'tampered_evidence_excluded', 'exact_evidence_restored', 'no_implicit_traditional_conversion', 'read_does_not_write'])


def validate_report(report, *, source_commit, binary_sha256, script_sha256):
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    require(isinstance(report, dict) and report.get("result") == "PASS", "CJK run failed")
    for key, expected in (("source_commit", source_commit), ("binary_sha256", binary_sha256), ("script_sha256", script_sha256)):
        require(report.get(key) == expected, "CJK provenance mismatch: " + key)
    require(report.get("tracked_tree_clean") is True, "CJK source tree not clean")
    checks = report.get("checks")
    require(isinstance(checks, list) and len(checks) == len(EXPECTED_CHECKS), "Incomplete CJK checks")
    require(all(isinstance(c, dict) and c.get("status") == "PASS" for c in checks), "Non-PASS CJK check")
    names = [c.get("name") for c in checks]
    require(set(names) == EXPECTED_CHECKS and len(set(names)) == len(names), "Wrong or duplicate CJK names")
    require(type(report.get("check_count")) is int and report["check_count"] == len(checks), "Wrong check count")
    counts = report.get("counts", {})
    require(counts == {"total": len(checks), "pass": len(checks), "fail": 0} and
            all(type(x) is int for x in counts.values()), "Wrong status counts")
    commands = report.get("commands")
    require(isinstance(commands, list) and len(commands) >= 54, "Incomplete command history")
    require(all(isinstance(c, dict) and type(c.get("exit_code")) is int and c["exit_code"] == 0 for c in commands),
            "Failed or incomplete child command")
    return len(checks)
