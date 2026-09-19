"""Evaluation-tool regressions; oracle answers here are fixtures, never model runs."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import memory_task_contract as c
import run_memory_tasks as r


def fixture(mode='with-context'):
    tasks = [{'case_id': case['id'], 'question': case['question'], 'context': '',
              'delivery_truncated': False} for case in c.CASES]
    packet = {'schema': 'qbrain-memory-task-packet-v1', 'run_id': 'a'*32,
              'mode': mode, 'instructions': c.INSTRUCTIONS, 'tasks': tasks}
    raw = c.encode(packet)
    expected = {}
    for case in c.CASES:
        state = c.EXPECTED_STATES[case['id']]
        n = 2 if state == 'conflict' else 1 if state == 'known' else 0
        expected[case['id']] = {'case_id': case['id'], 'state': state,
                               'values': [f'QBN47Q_fixture{i}' for i in range(n)],
                               'fact_ids': [str(i+1)*64 for i in range(n)]}
    key = {'schema': 'qbrain-memory-task-key-v1', 'run_id': 'a'*32, 'engine_ready': True,
           'corpus_sha256': c.digest(c.encode(c.CASES)), 'expected': expected,
           'packet_sha256': {mode: c.digest(raw)}}
    answers = [copy.deepcopy(expected[cid]) if mode == 'with-context'
               else {'case_id': cid, 'state': 'unknown', 'values': [], 'fact_ids': []} for cid in c.CASE_IDS]
    submitted = {'schema': 'qbrain-memory-task-answers-v1', 'run_id': 'a'*32,
                 'packet_sha256': c.digest(raw), 'answers': answers, 'usage': None}
    return key, raw, submitted


def evidence_fixture():
    fid, item, event = '1'*64, '2'*64, '3'*64
    wanted = {fid: {'quote': '我偏好标记QBN47Q_example。', 'item_id': item, 'event_id': event,
                    'predicate': 'memory.preference'}}
    fact = {'fact_id': fid, 'object': wanted[fid]['quote'], 'source_id': 'default',
            'subject': 'user', 'predicate': 'memory.preference', 'untrusted_data': True, 'status': 'active',
            'evidence': [{'item_id': item, 'event_id': event, 'source_id': 'default', 'method': 'explicit-markers-v1'}]}
    payload = {'fact_groups': [{'conflict_state': 'no_live_recorded_conflict', 'facts': [fact], 'contradictions': []}],
               'memories': [], 'truncated': False, 'source_id': 'default', 'untrusted_data': True,
               'fact_scope': 'direct_active_assertions'}
    return wanted, payload


class ScoringTests(unittest.TestCase):
    def test_fifty_fixed_cases_without_answer_hints(self):
        self.assertEqual(len(c.CASES), 50)
        self.assertEqual(len(set(c.CASE_IDS)), 50)
        for case in c.CASES:
            self.assertNotIn('QBN47Q_', case['question'])
            self.assertNotIn('fact_id', case['question'])

    def test_perfect_oracle_is_content_only_not_host_acceptance(self):
        for mode in ('with-context', 'without-context'):
            with self.subTest(mode=mode):
                result = c.score(*fixture(mode))
                self.assertEqual(result['correct'], 50)
                self.assertEqual(result['accuracy'], 1)
                for field in ('host_consumption_verified', 'usage_verified', 'evidence_authenticity_verified', 'general_answer_quality_verified'):
                    self.assertIs(result[field], False)
                self.assertIsNone(result['usage'])
                self.assertEqual(result['result'], 'ANSWER_CONTENT_SCORED')

    def test_missing_answers_stay_in_denominator(self):
        key, raw, submitted = fixture()
        submitted['answers'].pop()
        result = c.score(key, raw, submitted)
        self.assertEqual((result['total'], result['answered'], result['missing'], result['correct']), (50, 49, 1, 49))
        self.assertEqual(result['accuracy'], .98)
        submitted['answers'] = []
        result = c.score(key, raw, submitted)
        self.assertEqual(result['correct'], 0)
        self.assertEqual(result['missing'], 50)
        self.assertIs(result['complete'], False)

    def test_wrong_state_value_or_support_counts_wrong(self):
        for field, value in (('state', 'unknown'), ('values', ['invented']), ('fact_ids', ['f'*64])):
            with self.subTest(field=field):
                key, raw, submitted = fixture()
                submitted['answers'][0][field] = value
                self.assertEqual(c.score(key, raw, submitted)['correct'], 49)

    def test_unknown_not_equal_insufficient(self):
        key, raw, submitted = fixture()
        submitted['answers'][-1]['state'] = 'unknown'
        self.assertEqual(c.score(key, raw, submitted)['correct'], 49)

    def test_conflict_requires_both_values_and_supports(self):
        key, raw, submitted = fixture()
        row = next(x for x in submitted['answers'] if x['case_id'] == 'conflict-01')
        row['values'].pop(); row['fact_ids'].pop()
        self.assertEqual(c.score(key, raw, submitted)['correct'], 49)

    def test_answer_order_irrelevant_but_duplicates_rejected(self):
        key, raw, submitted = fixture()
        submitted['answers'].reverse()
        self.assertEqual(c.score(key, raw, submitted)['correct'], 50)
        submitted['answers'][-1] = copy.deepcopy(submitted['answers'][0])
        with self.assertRaises(ValueError): c.score(key, raw, submitted)

    def test_invalid_answer_fields_types_and_ids(self):
        for kind in ('extra', 'missing', 'state-bool', 'values-text', 'duplicate-value', 'duplicate-fact', 'invalid-fact', 'unknown-case'):
            with self.subTest(kind=kind):
                key, raw, submitted = fixture(); row = submitted['answers'][0]
                if kind == 'extra': row['confidence'] = 1
                if kind == 'missing': del row['state']
                if kind == 'state-bool': row['state'] = True
                if kind == 'values-text': row['values'] = 'not-an-array'
                if kind == 'duplicate-value': row['values'] *= 2
                if kind == 'duplicate-fact': row['fact_ids'] *= 2
                if kind == 'invalid-fact': row['fact_ids'] = ['NOT-A-FACT']
                if kind == 'unknown-case': row['case_id'] = 'other'
                with self.assertRaises(ValueError): c.score(key, raw, submitted)

    def test_run_packet_key_identities_and_engine_failure(self):
        for target, field, value in (('key', 'run_id', 'b'*32), ('key', 'engine_ready', False),
                                   ('key', 'engine_ready', 1), ('key', 'corpus_sha256', 'wrong'),
                                   ('submission', 'run_id', 'b'*32), ('submission', 'packet_sha256', 'wrong'),
                                   ('submission', 'schema', 'invented')):
            with self.subTest(target=target, field=field):
                key, raw, submitted = fixture()
                (key if target == 'key' else submitted)[field] = value
                with self.assertRaises(ValueError): c.score(key, raw, submitted)

    def test_changed_question_or_answer_in_control_rejected_even_with_new_hash(self):
        for kind in ('question', 'context', 'truncated', 'missing-task', 'reorder'):
            with self.subTest(kind=kind):
                key, raw, submitted = fixture('without-context'); packet = c.decode(raw)
                if kind == 'question': packet['tasks'][0]['question'] += ' ANSWER'
                if kind == 'context': packet['tasks'][0]['context'] = 'QBN47Q_hint'
                if kind == 'truncated': packet['tasks'][0]['delivery_truncated'] = True
                if kind == 'missing-task': packet['tasks'].pop()
                if kind == 'reorder': packet['tasks'].reverse()
                raw = c.encode(packet)
                key['packet_sha256']['without-context'] = c.digest(raw)
                submitted['packet_sha256'] = c.digest(raw)
                with self.assertRaises(ValueError): c.score(key, raw, submitted)

    def test_malformed_key_and_unobserved_states_rejected(self):
        for kind in ('missing', 'wrong-state', 'wrong-cardinality'):
            key, raw, submitted = fixture()
            if kind == 'missing': del key['expected'][c.CASE_IDS[0]]
            if kind == 'wrong-state': key['expected'][c.CASE_IDS[0]]['state'] = 'unknown'
            if kind == 'wrong-cardinality': key['expected'][c.CASE_IDS[0]]['values'] = []
            with self.assertRaises(ValueError): c.score(key, raw, submitted)

    def test_usage_is_optional_nullable_and_unverified(self):
        key, raw, submitted = fixture()
        submitted['usage'] = {'source': 'provider_reported', 'input_tokens': 45, 'output_tokens': 12, 'cost_usd': None}
        result = c.score(key, raw, submitted)
        self.assertEqual(result['usage']['input_tokens'], 45)
        self.assertIsNone(result['usage']['cost_usd'])
        self.assertIs(result['usage_verified'], False)

    def test_usage_rejects_boolean_negative_nan_infinity_and_huge_cost(self):
        for field, value in (('input_tokens', True), ('output_tokens', -1), ('input_tokens', 1.5),
                             ('cost_usd', float('nan')), ('cost_usd', float('inf')), ('cost_usd', True),
                             ('cost_usd', 10**999), ('source', 'chars-divided-by-four')):
            with self.subTest(field=field, value=str(value)[:12]):
                key, raw, submitted = fixture()
                submitted['usage'] = {'source': 'provider_reported', 'input_tokens': None, 'output_tokens': None, 'cost_usd': None}
                submitted['usage'][field] = value
                with self.assertRaises(ValueError): c.score(key, raw, submitted)

    def test_bad_utf8_duplicate_keys_nonfinite_and_size(self):
        for raw in (b'\xff', b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'['*2000):
            with self.subTest(raw=raw[:20]):
                with self.assertRaises(ValueError): c.decode(raw)
        with patch.object(c, 'MAX_BYTES', 2):
            with self.assertRaises(ValueError): c.decode(b'{} ')

    def test_exclusive_reports_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'old.json'; path.write_bytes(b'KEEP')
            with self.assertRaises(FileExistsError): c.write_new(path, {'new': 1})
            self.assertEqual(path.read_bytes(), b'KEEP')

    def test_cli_missing_answers_not_pass_and_existing_report_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); key, raw, submitted = fixture(); submitted['answers'] = []
            (root/'key.json').write_bytes(c.encode(key)); (root/'packet.json').write_bytes(raw)
            (root/'answers.json').write_bytes(c.encode(submitted))
            argv = [sys.executable, str(Path(__file__).with_name('score_memory_tasks.py')),
                    '--key', str(root/'key.json'), '--packet', str(root/'packet.json'),
                    '--answers', str(root/'answers.json'), '--report', str(root/'report.json')]
            self.assertEqual(subprocess.run(argv, capture_output=True).returncode, 1)
            before = (root/'report.json').read_bytes()
            self.assertEqual(subprocess.run(argv, capture_output=True).returncode, 2)
            self.assertEqual((root/'report.json').read_bytes(), before)


class EngineChecks(unittest.TestCase):
    def test_exact_evidence_positive(self):
        wanted, payload = evidence_fixture()
        r.verify_evidence(payload, wanted, 'known')
        envelope = {'hookSpecificOutput': {'hookEventName': 'SessionStart',
                    'additionalContext': r.CONTEXT_PREFIX + json.dumps(payload, ensure_ascii=False)}}
        self.assertEqual(r.parse_context(envelope)[1], payload)

    def test_evidence_identity_permission_and_role_mutations_rejected(self):
        for kind in ('quote', 'source', 'predicate', 'status', 'untrusted', 'subject', 'event', 'item',
                     'support-source', 'method', 'missing', 'raw-bypass', 'conflict-enum'):
            with self.subTest(kind=kind):
                wanted, payload = evidence_fixture(); fact = payload['fact_groups'][0]['facts'][0]
                if kind == 'quote': fact['object'] += 'changed'
                if kind == 'source': fact['source_id'] = 'another'
                if kind == 'predicate': fact['predicate'] = 'another'
                if kind == 'status': fact['status'] = 'retracted'
                if kind == 'untrusted': fact['untrusted_data'] = False
                if kind == 'subject': fact['subject'] = 'assistant'
                if kind == 'event': fact['evidence'][0]['event_id'] = '4'*64
                if kind == 'item': fact['evidence'][0]['item_id'] = '4'*64
                if kind == 'support-source': fact['evidence'][0]['source_id'] = 'another'
                if kind == 'method': fact['evidence'][0]['method'] = 'model'
                if kind == 'missing': payload['fact_groups'] = []
                if kind == 'raw-bypass': payload['memories'] = [{}]
                if kind == 'conflict-enum': payload['fact_groups'][0]['conflict_state'] = 'not_recorded_conflict'
                with self.assertRaises(ValueError): r.verify_evidence(payload, wanted, 'known')

    def test_empty_output_not_proof_of_no_memory(self):
        _, payload = r.parse_context({})
        r.verify_evidence(payload, {}, 'unknown')
        wanted, _ = evidence_fixture()
        with self.assertRaises(ValueError): r.verify_evidence(payload, wanted, 'known')

    def test_bad_hook_context_rejected(self):
        for envelope in ([], {'hookSpecificOutput': {}}, {'hookSpecificOutput': {'hookEventName': 'Stop', 'additionalContext': 'anything'}}):
            with self.assertRaises(ValueError): r.parse_context(envelope)

    def test_subprocess_nonzero_bad_json_and_byte_limit(self):
        for code, cap in (("raise SystemExit(9)", r.OUTPUT_CAP), ("print('not-json')", r.OUTPUT_CAP), ("print('12345')", 2)):
            with tempfile.TemporaryDirectory() as d:
                root = Path(d); output = root/'out'; output.mkdir()
                engine = r.Engine(Path(sys.executable), root, output)
                with patch.object(r, 'OUTPUT_CAP', cap):
                    with self.assertRaises(ValueError): engine.invoke('fixture', ['-c', code], root)
                self.assertEqual(len(engine.commands), 1)

    def test_timeout_cannot_become_success(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); output = root/'out'; output.mkdir()
            engine = r.Engine(Path(sys.executable), root, output)
            with patch.object(r.subprocess, 'run', side_effect=subprocess.TimeoutExpired('fixture', 30)):
                with self.assertRaises(ValueError): engine.invoke('fixture', [], root)
            self.assertIsNone(engine.commands[0]['exit'])
            self.assertIs(engine.commands[0]['timed_out'], True)

    def test_environment_scrub_and_no_existing_output(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); output = root/'out'; output.mkdir()
            with patch.dict(r.os.environ, {'QBRAIN_BRAIN': 'real', 'OPENAI_API_KEY': 'not-real', 'ANTHROPIC_API_KEY': 'not-real'}):
                engine = r.Engine(Path(sys.executable), root, output)
                self.assertNotIn('QBRAIN_BRAIN', engine.env)
                self.assertNotIn('OPENAI_API_KEY', engine.env)
                self.assertNotIn('ANTHROPIC_API_KEY', engine.env)
            with self.assertRaises(FileExistsError): r.run(Path(sys.executable), output, 'claude')


if __name__ == '__main__':
    unittest.main(verbosity=2)
