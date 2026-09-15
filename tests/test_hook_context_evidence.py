"""Acceptance-helper regressions; these do not certify live client execution."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hook_inspector", ROOT / "tools/acceptance/inspect_hook_context.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def group(state="no_live_recorded_conflict", quote="synthetic private quote"):
    return {"conflict_state": state, "facts": [{"object": quote}] * (2 if state == "recorded_conflict" else 1),
            "contradictions": [{"relation": "contradicts"}] if state == "recorded_conflict" else []}


def context(groups=None, truncated=False):
    payload = {"source_id": "synthetic-source", "untrusted_data": True,
               "fact_scope": "direct_active_assertions", "fact_groups": groups if groups is not None else [group()],
               "memories": [], "truncated": truncated}
    return m.PREFIX + json.dumps(payload, ensure_ascii=False)


def raw(groups=None, truncated=False, event="SessionStart"):
    return json.dumps({"hookSpecificOutput": {"hookEventName": event,
                     "additionalContext": context(groups, truncated)}}, ensure_ascii=False).encode("utf-8")


class HookContextEvidenceTests(unittest.TestCase):
    def test_no_live_does_not_count_as_recorded(self):
        self.assertIn("recorded_conflict", "no_live_recorded_conflict")
        r = m.inspect(raw())
        self.assertEqual(r["recorded_conflict_groups"], 0)
        self.assertEqual(r["no_live_recorded_conflict_groups"], 1)

    def test_recorded_exact_state(self):
        r = m.inspect(raw([group("recorded_conflict")]))
        self.assertEqual(r["recorded_conflict_groups"], 1)
        self.assertEqual(r["no_live_recorded_conflict_groups"], 0)

    def test_user_quotes_do_not_determine_state(self):
        r = m.inspect(raw([group(quote='recorded_conflict and \"conflict_state\":\"recorded_conflict\"')]))
        self.assertEqual(r["recorded_conflict_groups"], 0)
        self.assertNotIn("synthetic private quote", json.dumps(r))

    def test_mixed_groups_count_individually(self):
        r = m.inspect(raw([group(), group("recorded_conflict"), group()]))
        self.assertEqual(r["fact_group_count"], 3)
        self.assertEqual(r["recorded_conflict_groups"], 1)
        self.assertEqual(r["no_live_recorded_conflict_groups"], 2)

    def test_empty_envelope_is_not_no_conflict_proof(self):
        r = m.inspect(b"{}")
        self.assertFalse(r["context_present"])
        self.assertIsNone(r["truncated"])
        self.assertFalse(r["absence_proven"])

    def test_empty_truncated_context_is_incomplete(self):
        r = m.inspect(raw([], truncated=True))
        self.assertTrue(r["context_present"])
        self.assertTrue(r["truncated"])
        self.assertFalse(r["absence_proven"])

    def test_additional_context_mode(self):
        r = m.inspect(context([group("recorded_conflict")]).encode(), "additional-context")
        self.assertIsNone(r["event"])
        self.assertEqual(r["recorded_conflict_groups"], 1)

    def test_both_supported_events(self):
        for name in ("SessionStart", "UserPromptSubmit"):
            self.assertEqual(m.inspect(raw(event=name))["event"], name)
        for name in ("Stop", "SessionEnd", "", None, True):
            with self.subTest(name=name), self.assertRaises(m.EvidenceError):
                m.inspect(raw(event=name))

    def test_unknown_state_fails(self):
        for state in ("not_recorded_conflict", "RECORDED_CONFLICT", "recorded_conflict ", True, None):
            g = group(); g["conflict_state"] = state
            with self.subTest(state=state), self.assertRaises(m.EvidenceError): m.inspect(raw([g]))

    def test_inconsistent_state_structure_fails(self):
        for g in ({"conflict_state":"recorded_conflict","facts":[{}],"contradictions":[]},
                  {"conflict_state":"no_live_recorded_conflict","facts":[{},{}],"contradictions":[{}]},
                  {"conflict_state":"recorded_conflict","facts":"wrong","contradictions":[{}]}):
            with self.subTest(group=g), self.assertRaises(m.EvidenceError): m.inspect(raw([g]))

    def test_summary_flags_and_prose_are_not_raw_hook_evidence(self):
        for value in (b'{"contains_recorded_conflict":true}', b'{"result":"recorded_conflict"}',
                      b'"no_live_recorded_conflict"', b'[]', b'A model says recorded_conflict'):
            with self.subTest(value=value), self.assertRaises(m.EvidenceError): m.inspect(value)

    def test_duplicate_keys_are_rejected_at_both_levels(self):
        for value in ('{"hookSpecificOutput":{},"hookSpecificOutput":{}}',
                      m.PREFIX + '{"fact_scope":"a","fact_scope":"b"}'):
            with self.subTest(value=value), self.assertRaises(m.EvidenceError):
                m.inspect(value.encode(), "additional-context" if value.startswith(m.PREFIX) else "hook-output")

    def test_bad_utf8_nul_and_size(self):
        for b in (b'\xff', b'{}\0', b'x' * (m.MAX_INPUT_BYTES + 1)):
            with self.subTest(size=len(b)), self.assertRaises(m.EvidenceError): m.inspect(b)
        self.assertEqual(m.inspect(b'\xef\xbb\xbf{}')["result"], "INSPECTED")

    def test_nonfinite_and_deep_json(self):
        for b in (b'{"n":NaN}', b'{"n":Infinity}', b'{"n":' + b'[' * 1100 + b']' * 1100 + b'}'):
            with self.subTest(size=len(b)), self.assertRaises(m.EvidenceError): m.inspect(b)

    def test_no_quote_source_or_marker_echo(self):
        text = 'QBN47E-synthetic-secret-marker 中文'
        r = m.inspect(raw([group(quote=text)]))
        serialized = json.dumps(r)
        self.assertNotIn(text, serialized)
        self.assertNotIn("synthetic-source", serialized)
        self.assertFalse(r["host_consumption_verified"])
        self.assertFalse(r["evidence_authenticity_verified"])
        self.assertFalse(r["fact_evidence_validated"])

    def test_protocol_type_and_count_bounds(self):
        for edit in (lambda p: p.update(truncated=0), lambda p: p.update(untrusted_data=1),
                     lambda p: p.update(fact_scope="all"), lambda p: p.update(memories=None),
                     lambda p: p.update(fact_groups=[group()] * 17), lambda p: p.update(source_id=None)):
            p = json.loads(context()[len(m.PREFIX):]); edit(p)
            with self.subTest(edit=edit), self.assertRaises(m.EvidenceError):
                m.inspect((m.PREFIX + json.dumps(p)).encode(), "additional-context")

    def test_existing_report_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            source, out = Path(d)/"input.json", Path(d)/"report.json"
            source.write_bytes(raw()); out.write_bytes(b"preserve")
            self.assertEqual(m.main(["--input",str(source),"--report",str(out)]), 2)
            self.assertEqual(out.read_bytes(), b"preserve")
            self.assertEqual(source.read_bytes(), raw())

    def test_cli_returns_typed_result_without_changing_input(self):
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()):
            source, out = Path(d)/"input.json", Path(d)/"report.json"
            source.write_bytes(raw())
            self.assertEqual(m.main(["--input",str(source),"--report",str(out)]), 0)
            r = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(r["result"], "INSPECTED")
            self.assertEqual(r["recorded_conflict_groups"], 0)
            self.assertEqual(source.read_bytes(), raw())

    def test_failure_report_does_not_echo_bad_input(self):
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()):
            source, out = Path(d)/"input.json", Path(d)/"report.json"
            source.write_bytes(b"synthetic-private-data-not-json")
            self.assertEqual(m.main(["--input",str(source),"--report",str(out)]), 1)
            text = out.read_text(encoding="utf-8")
            self.assertNotIn("synthetic-private-data", text)
            self.assertEqual(json.loads(text)["result"], "REJECTED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
