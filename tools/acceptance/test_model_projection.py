"""Separate nonempty-context regressions: session labels must not reveal cases."""
import copy
import json
import unittest

import memory_task_contract as c
import model_ab as m
from run_memory_tasks import CONTEXT_PREFIX
from test_memory_tasks import evidence_fixture
from test_model_ab import Setup


class ProjectionTests(Setup):
    def prepared_context(self):
        _, payload = evidence_fixture()
        payload['fact_groups'][0]['facts'][0]['evidence'][0]['session_id'] = 'seed-preference-01'
        raw = CONTEXT_PREFIX + json.dumps(payload, ensure_ascii=False)
        packet = c.decode((self.inputs / 'with-context.json').read_bytes())
        packet['tasks'][0]['context'] = raw
        packet_raw = c.encode(packet)
        (self.inputs / 'with-context.json').write_bytes(packet_raw)
        self.key['packet_sha256']['with-context'] = c.digest(packet_raw)
        self.key_path.write_bytes(c.encode(self.key))
        return payload, packet_raw

    def test_nonempty_evidence_hides_session_labels_and_keeps_original_packet(self):
        payload, original_packet = self.prepared_context()
        p = self.plan()
        self.assertEqual(p['packet_text']['with-context'].encode(), original_packet)
        packets = m.validate_plan(p)
        row = next(x for x in p['rows'] if x['case_id'] == 'preference-01' and x['mode'] == 'with-context')
        raw = m.request_body(p, packets, row)
        self.assertNotIn(b'preference-01', raw)
        task = c.decode(c.decode(raw)['messages'][-1]['content'].encode())
        projected = c.decode(task['context'][len(CONTEXT_PREFIX):].encode())
        expected = copy.deepcopy(payload)
        session = projected['fact_groups'][0]['facts'][0]['evidence'][0]['session_id']
        self.assertRegex(session, r'^session-[0-9a-f]{32}$')
        expected['fact_groups'][0]['facts'][0]['evidence'][0]['session_id'] = session
        self.assertEqual(projected, expected)
        self.assertEqual((self.inputs / 'with-context.json').read_bytes(), original_packet)
        self.assertEqual(m.request_body(p, packets, row), raw)

    def test_projection_bound_to_plan_and_preserves_literal_user_text(self):
        payload, _ = self.prepared_context()
        # User text is evidence, not testing metadata: never rewrite it.
        payload['fact_groups'][0]['facts'][0]['object'] = 'I literally chose seed-preference-01.'
        text = CONTEXT_PREFIX + c.encode(payload).decode()
        first = m.projected_context(text, 'a'*32)
        self.assertIn('I literally chose seed-preference-01.', first)
        self.assertEqual(first, m.projected_context(text, 'a'*32))
        self.assertNotEqual(first, m.projected_context(text, 'b'*32))
        p = self.plan(); p['context_projection'] = 'disabled'
        with self.assertRaises(ValueError): m.validate_plan(p)
        self.assertEqual(m.projected_context('', 'a'*32), '')

    def test_unrecognized_context_and_malformed_session_rejected(self):
        with self.assertRaises(ValueError): m.projected_context('unrecognized raw input', 'a'*32)
        payload, _ = self.prepared_context()
        for value in (None, False, 12, '', [], 'x'*257):
            with self.subTest(value=str(value)[:20]):
                payload['fact_groups'][0]['facts'][0]['evidence'][0]['session_id'] = value
                with self.assertRaises(ValueError):
                    m.projected_context(CONTEXT_PREFIX + c.encode(payload).decode(), 'a'*32)


if __name__ == '__main__': unittest.main(verbosity=2)
