"""N48L contract and real native/HTTP integration tests. Synthetic, never model evidence."""
from __future__ import annotations

import argparse
import copy
from fractions import Fraction
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import itertools
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import memory_task_contract as c
import model_ab as m
import model_cost as b
import model_evaluation as e
from test_memory_tasks import fixture
from test_model_cost import plan, price, response

BINARY = None
EVIDENCE = None


def make_key(p):
    key = fixture()[0]
    key['packet_sha256'] = {mode: c.digest(p['packet_text'][mode].encode()) for mode in m.MODES}
    return key


def answer_for(key, row, profile):
    cid, mode = row['case_id'], row['mode']
    if callable(profile):
        a = profile(key, row)
    elif profile == 'perfect':
        a = copy.deepcopy(key['expected'][cid]) if mode == 'with-context' else dict(case_id=cid, state='unknown', values=[], fact_ids=[])
    elif profile == 'abstain':
        a = dict(case_id=cid, state='unknown', values=[], fact_ids=[])
    elif profile == 'same-failures':
        if c.EXPECTED_STATES[cid] in ('known', 'conflict'):
            a = dict(case_id=cid, state='known', values=['QBN47Q_wrong_value'], fact_ids=['f'*64])
        else:
            a = copy.deepcopy(key['expected'][cid]) if mode == 'with-context' else dict(case_id=cid, state='unknown', values=[], fact_ids=[])
    else:
        raise ValueError('unknown fixture profile')
    return {**a, 'case_id': row['request_id']}


def build_run(directory, profile='perfect', candidate_input=100, fail_at=None, unknown_cache=False, drift=False):
    p = plan()
    key = make_key(p)
    i = 0
    def post(_plan, _body, _key):
        nonlocal i
        row = p['rows'][i]; i += 1
        if fail_at == i:
            return 503, b''
        value = response(row, candidate_input if row['mode'] == 'with-context' else 100)
        value['choices'][0]['message']['content'] = json.dumps(answer_for(key, row, profile))
        if unknown_cache:
            value['usage']['prompt_tokens_details']['cached_tokens'] = None
        if drift and row['mode'] == 'with-context':
            value['model'] = 'different-model'
        return 200, c.encode(value)
    raw = c.encode(p)
    with patch.object(m, 'post', side_effect=post):
        m.run(raw, directory, approved_sha=c.digest(raw), approved_endpoint=p['endpoint'], request_cap=m.COUNT)
    return key


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='qbrain-n48l-base-')
        cls.base = Path(cls.temp.name)/'run'
        cls.key = build_run(cls.base)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='qbrain-n48l-tests-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root/'run'; shutil.copytree(self.base, self.run)
        self.key_path = self.root/'offline-key.json'; self.key_path.write_bytes(c.encode(self.key))
        self.rates = self.root/'rates.json'; self.rates.write_bytes(b.encode(price()))
        self.output = self.root/'evaluation'

    def analyze(self):
        return e.analyze(self.run, self.key_path, self.rates, BINARY)

    def remake(self, **kwargs):
        shutil.rmtree(self.run)
        key = build_run(self.run, **kwargs)
        self.key_path.write_bytes(c.encode(key))

    def execute(self, verify=False):
        return e.execute(self.run, self.key_path, self.rates, BINARY, self.output, verify)

    def test_01_resolution_is_not_grounded_abstention(self):
        report, _ = self.analyze()
        baseline, candidate = [report['arms'][mode] for mode in e.MODES]
        self.assertEqual(baseline['packet_grounded']['count'], 50)
        self.assertEqual(candidate['packet_grounded']['count'], 50)
        self.assertEqual(baseline['answerable_resolution']['count'], 0)
        self.assertEqual(candidate['answerable_resolution']['count'], 25)
        self.assertEqual(report['paired']['answerable_resolution'], dict(improved=25, regressed=0, both_correct=0, both_incorrect=0, total=25))
        self.assertEqual(report['decision']['result'], 'CANDIDATE_DOMINATES_OBSERVED_CASES')
        self.assertEqual(report['changes']['answerable_resolution_rate'], dict(numerator='1', denominator='1'))
        self.assertEqual(report['changes']['packet_grounded_rate'], dict(numerator='0', denominator='1'))

    def test_02_cheaper_abstainer_is_not_an_improvement(self):
        self.remake(profile='abstain', candidate_input=50)
        report, _ = self.analyze()
        self.assertEqual(report['arms']['with-context']['answerable_resolution']['count'], 0)
        self.assertEqual(report['arms']['with-context']['packet_grounded']['count'], 20)
        self.assertLess(Fraction(report['changes']['main_cost']['candidate_minus_baseline']), 0)
        self.assertEqual(report['decision']['result'], 'TRADEOFF_OBSERVED')
        self.assertFalse(report['decision']['candidate_dominates_observed_cases'])

    def test_03_more_resolution_but_more_expensive_is_a_tradeoff(self):
        self.remake(candidate_input=150)
        report, _ = self.analyze()
        self.assertEqual(report['paired']['answerable_resolution']['improved'], 25)
        self.assertGreater(Fraction(report['changes']['main_cost']['candidate_minus_baseline']), 0)
        self.assertEqual(report['decision']['result'], 'TRADEOFF_OBSERVED')

    def test_04_same_quality_cheaper_or_dearer_and_no_change(self):
        for quantity, decision in ((50, 'CANDIDATE_DOMINATES_OBSERVED_CASES'),
                                   (100, 'NO_CHANGE_OBSERVED'), (150, 'BASELINE_DOMINATES_OBSERVED_CASES')):
            self.remake(profile='same-failures', candidate_input=quantity)
            with self.subTest(quantity=quantity):
                r, _ = self.analyze()
                self.assertEqual(r['decision']['result'], decision)
                self.assertEqual(r['arms']['with-context']['answerable_resolution']['count'], 0)
                self.assertFalse(r['quality_preserving_savings_verified'])

    def test_05_paired_regression_not_hidden_by_aggregate_gain(self):
        def profile(key, row):
            cid, mode = row['case_id'], row['mode']
            if mode == 'without-context':
                return (dict(case_id=cid, state='known', values=['QBN47Q_wrong'], fact_ids=['f'*64])
                        if cid == 'forget-01' else dict(case_id=cid, state='unknown', values=[], fact_ids=[]))
            return (dict(case_id=cid, state='known', values=['QBN47Q_wrong'], fact_ids=['f'*64])
                    if cid == 'forget-02' else copy.deepcopy(key['expected'][cid]))
        self.remake(profile=profile, candidate_input=50)
        r, _ = self.analyze()
        self.assertEqual(r['arms']['without-context']['packet_grounded']['count'], 49)
        self.assertEqual(r['arms']['with-context']['packet_grounded']['count'], 49)
        self.assertEqual((r['paired']['packet_grounded']['improved'],r['paired']['packet_grounded']['regressed']), (1,1))
        self.assertEqual(r['decision']['result'], 'TRADEOFF_OBSERVED')
        self.assertFalse(r['decision']['candidate_no_quality_regressions'])

    def test_06_exact_cost_per_resolution_zero_is_null(self):
        r, _ = self.analyze()
        a = r['arms']['without-context']['cost_per_resolved_task']
        self.assertIsNone(a['amount']); self.assertEqual(a['unavailable_reason'], 'zero_resolved_tasks')
        a = r['arms']['with-context']['cost_per_resolved_task']
        expected = 50 * (80*Fraction('1.234567')+20*Fraction('0.123456')+20*Fraction('3.456789'))/10**6/25
        self.assertEqual(a['amount'], e.fraction(expected))
        self.assertIsNone(a['unavailable_reason'])

    def test_07_missing_rates_withholds_differences(self):
        p = price(); p['rates'] = []; self.rates.write_bytes(b.encode(p))
        r, _ = self.analyze()
        self.assertEqual(r['decision']['result'], 'NOT_COMPARABLE')
        self.assertIn('cost_components_unknown', r['decision']['unavailable_reasons'])
        self.assertIsNone(r['changes']['answerable_resolution_rate'])
        self.assertIsNone(r['arms']['with-context']['cost_per_resolved_task']['amount'])
        self.assertEqual(r['arms']['with-context']['answerable_resolution']['count'], 25)

    def test_08_unknown_cache_is_not_zero(self):
        self.remake(unknown_cache=True)
        r, _ = self.analyze()
        self.assertEqual(r['decision']['result'], 'NOT_COMPARABLE')
        self.assertIn('cost_components_unknown', r['decision']['unavailable_reasons'])
        self.assertIsNone(r['changes']['main_cost']['candidate_minus_baseline'])

    def test_09_partial_execution_fixed_denominators(self):
        self.remake(fail_at=2)
        r, _ = self.analyze()
        self.assertEqual((r['attempted_requests'],r['completed_responses']), (2,1))
        self.assertEqual(r['decision']['result'], 'NOT_COMPARABLE')
        self.assertEqual(sum(x['answered'] for x in r['arms'].values()), 1)
        self.assertEqual(sum(x['missing_or_failed'] for x in r['arms'].values()), 99)
        for x in r['arms'].values():
            self.assertEqual(x['packet_grounded']['total'], 50)
            self.assertEqual(x['answerable_resolution']['total'], 25)
        self.assertEqual(len(r['cases']),50)
        self.assertIsNone(r['changes']['main_cost'])

    def test_10_last_failure_still_has_no_dominance(self):
        self.remake(fail_at=100)
        r, _ = self.analyze()
        self.assertEqual((r['attempted_requests'],r['completed_responses']), (100,99))
        self.assertEqual(r['decision']['result'], 'NOT_COMPARABLE')
        self.assertIsNone(r['decision']['candidate_dominates_observed_cases'])
        self.assertIsNone(r['changes']['main_cost']['candidate_minus_baseline'])

    def test_11_model_drift_retains_scores_but_no_decision(self):
        self.remake(drift=True)
        p = price(); card=copy.deepcopy(p['rates'][0]); card.update(model='different-model',rate_id='different')
        p['rates'].append(card); self.rates.write_bytes(b.encode(p))
        r, _ = self.analyze()
        self.assertIn('primary_model_mismatch', r['decision']['unavailable_reasons'])
        self.assertEqual(r['decision']['result'], 'NOT_COMPARABLE')

    def test_12_strict_key_binding(self):
        original = self.key_path.read_bytes()
        for field, value in (('run_id','b'*32), ('engine_ready', True), ('corpus_sha256','0'*64)):
            if field == 'engine_ready': value=1
            k=c.decode(original); k[field]=value; self.key_path.write_bytes(c.encode(k))
            with self.subTest(field=field):
                with self.assertRaises(ValueError): self.analyze()
            self.key_path.write_bytes(original)
        k=c.decode(original); k['packet_sha256']['without-context']='0'*64
        self.key_path.write_bytes(c.encode(k))
        with self.assertRaises(ValueError): self.analyze()
        self.assertFalse(self.output.exists())

    def test_13_key_json_duplicate_nonfinite_and_encoding(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}',b'{"x":"\\ud800"}',b'['*50+b'0'+b']'*50,b'\xff'):
            self.key_path.write_bytes(raw)
            with self.subTest(raw=raw[:30]):
                with self.assertRaises(ValueError): self.analyze()

    def test_14_wrong_answers_are_scored_not_rejected_or_hidden(self):
        k=c.decode(self.key_path.read_bytes())
        # Still shape-valid but wrong key content changes score; input key is not authenticated.
        k['expected']['preference-01']['values']=['QBN47Q_changed_offline_key']
        self.key_path.write_bytes(c.encode(k))
        r,_=self.analyze()
        self.assertEqual(r['arms']['with-context']['packet_grounded']['count'],49)
        self.assertEqual(r['arms']['with-context']['answerable_resolution']['count'],24)
        self.assertFalse(r['evaluator_key_authenticated'])

    def test_15_no_answer_key_or_prompt_export(self):
        r, outputs=self.analyze()
        raw=b''.join(outputs.values())
        for secret in (b'QBN47Q_fixture',b'"expected"',b'"values"',b'"fact_ids"',b'packet_text',b'19481',str(self.key_path).encode()):
            self.assertNotIn(secret,raw)
        for field in ('quality_preserving_savings_verified','general_answer_quality_verified','statistical_generalization_verified',
                      'source_provenance_authenticated','host_consumption_verified','billing_verified','full_pipeline_costs_included'):
            self.assertIs(r[field],False)
        self.assertEqual(r['execution_kind'],'LOOPBACK_TEST')

    def test_16_no_network_or_executor_or_disk_scoring(self):
        native = b.Native.invoke
        seen=[]
        def checked(obj, action, value):
            encoded=b.encode(value)
            self.assertNotIn(b'QBN47Q_fixture',encoded); self.assertNotIn(b'"expected"',encoded)
            seen.append(action)
            return native(obj,action,value)
        with patch.object(m,'run',side_effect=AssertionError('executor forbidden')), \
             patch.object(m,'post',side_effect=AssertionError('HTTP forbidden')), \
             patch.object(m,'score_run',side_effect=AssertionError('disk scoring forbidden')), \
             patch.object(socket,'create_connection',side_effect=AssertionError('network forbidden')), \
             patch.object(b.Native,'invoke',checked):
            r,_=self.analyze()
        self.assertEqual(r['provider_requests_sent_by_evaluator'],0)
        self.assertIn('compare',seen)

    def test_17_source_and_key_unchanged_after_export_verify(self):
        before={p.relative_to(self.run).as_posix():p.read_bytes() for p in self.run.rglob('*') if p.is_file()}
        key=self.key_path.read_bytes(); rates=self.rates.read_bytes()
        self.assertEqual(self.execute()['result'],'EXPORTED')
        self.assertEqual(self.execute(True)['result'],'VERIFIED')
        self.assertEqual(before,{p.relative_to(self.run).as_posix():p.read_bytes() for p in self.run.rglob('*') if p.is_file()})
        self.assertEqual(key,self.key_path.read_bytes()); self.assertEqual(rates,self.rates.read_bytes())

    def test_18_no_overwrite_or_output_in_input(self):
        self.output.mkdir(); (self.output/'sentinel').write_bytes(b'unchanged')
        with self.assertRaisesRegex(b.Reject,'output_exists'): self.execute()
        self.assertEqual((self.output/'sentinel').read_bytes(),b'unchanged')
        with self.assertRaisesRegex(b.Reject,'output_inside_source'):
            e.execute(self.run,self.key_path,self.rates,BINARY,self.run/'nested')
        self.assertFalse((self.run/'nested').exists())

    def test_19_change_source_between_score_and_cost_is_rejected(self):
        real=b.analyze
        def mutate(*args):
            path=self.run/'run.json'; v=c.decode(path.read_bytes()); v['completed']=1; path.write_bytes(c.encode(v))
            return real(*args)
        with patch.object(b,'analyze',side_effect=mutate):
            with self.assertRaises(ValueError): self.execute()
        self.assertFalse(self.output.exists())

    def test_20_matching_cost_manifest_is_mandatory(self):
        real=b.analyze
        def mutate(*args):
            result, files=real(*args); source=b.decode(files['source-manifest.json']); source['files']['plan.json']['sha256']='0'*64
            files['source-manifest.json']=b.encode(source)
            return result,files
        with patch.object(b,'analyze',side_effect=mutate):
            with self.assertRaisesRegex(b.Reject,'source_mismatch'): self.execute()
        self.assertFalse(self.output.exists())

    def test_21_key_mutation_during_pricing(self):
        real=b.analyze
        def mutate(*args):
            result=real(*args); self.key_path.write_bytes(b'{}'); return result
        with patch.object(b,'analyze',side_effect=mutate):
            with self.assertRaisesRegex(b.Reject,'key_changed'): self.execute()
        self.assertFalse(self.output.exists())

    def test_22_bundle_mutations_even_when_rehashed(self):
        self.execute(); original={p.name:p.read_bytes() for p in self.output.iterdir()}
        for variant in ('grounded','resolved','dominance','bool','scope','ratio','key-digest','cost','missing','extra','duplicate'):
            for p in self.output.iterdir(): p.unlink()
            for name,raw in original.items(): (self.output/name).write_bytes(raw)
            name='evaluation.json'; obj=b.decode(original[name])
            if variant=='grounded': obj['arms']['with-context']['packet_grounded']['count']=0
            elif variant=='resolved': obj['arms']['without-context']['answerable_resolution']['count']=25
            elif variant=='dominance': obj['decision']['result']='BASELINE_DOMINATES_OBSERVED_CASES'
            elif variant=='bool': obj['planned_requests']=True
            elif variant=='scope': obj['quality_preserving_savings_verified']=True
            elif variant=='ratio': obj['arms']['with-context']['cost_per_resolved_task']['amount']['numerator']='0'
            elif variant=='key-digest': name='provenance.json'; obj=b.decode(original[name]); obj['evaluator_key_sha256']='0'*64
            elif variant=='cost': name='cost-analysis.json'; obj=b.decode(original[name]); obj['comparison']['change']['candidate_minus_baseline']='-1.000000000000'
            elif variant=='missing': (self.output/'quality-scores.json').unlink()
            elif variant=='extra': (self.output/'unexpected').write_bytes(b'{}')
            raw=b.encode(obj) if variant!='duplicate' else b'{"schema":"wrong",'+original[name][1:]
            if variant not in ('missing','extra'):
                (self.output/name).write_bytes(raw); manifest=b.decode(original['MANIFEST.json'])
                manifest['files'][name]={'bytes':len(raw),'sha256':b.sha(raw)}
                (self.output/'MANIFEST.json').write_bytes(b.encode(manifest))
            with self.subTest(variant=variant):
                with self.assertRaises(b.Reject): self.execute(True)

    def test_23_symlink_keys_and_export_parent(self):
        link=self.root/'key-link'
        try: link.symlink_to(self.key_path)
        except OSError as ex: self.skipTest('Symlink creation not available: '+type(ex).__name__)
        with self.assertRaisesRegex(b.Reject,'link_input'):
            e.analyze(self.run,link,self.rates,BINARY)
        link.unlink(); link.symlink_to(self.root,target_is_directory=True)
        with self.assertRaisesRegex(b.Reject,'link_input'):
            e.execute(self.run,self.key_path,self.rates,BINARY,link/'new')

    def test_24_cli_roundtrip_and_redacted_errors(self):
        cmd=[sys.executable,str(Path(e.__file__)),'export','--run',str(self.run),'--key',str(self.key_path),
             '--rates',str(self.rates),'--binary',str(BINARY),'--output',str(self.output)]
        p=subprocess.run(cmd,capture_output=True,timeout=90)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr); self.assertEqual(p.stderr,b'')
        cmd[2]='verify'; p=subprocess.run(cmd,capture_output=True,timeout=90)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.key_path.write_bytes(b'{"private":"DO-NOT-ECHO"}')
        p=subprocess.run(cmd,capture_output=True,timeout=90)
        self.assertEqual(p.returncode,2); self.assertEqual(p.stderr,b'')
        self.assertNotIn(b'DO-NOT-ECHO',p.stdout); self.assertNotIn(str(self.root).encode(),p.stdout)

    def test_25_original_scores_and_costs_are_preserved(self):
        _, outputs=self.analyze()
        expected=m.score_run(self.run,self.key_path)['scores']
        self.assertEqual(b.decode(outputs['quality-scores.json']),expected)
        _, old=b.analyze(self.run,self.rates,BINARY)
        self.assertEqual(outputs['cost-analysis.json'],old['analysis.json'])
        self.assertEqual(outputs['comparison-input.json'],old['comparison-input.json'])


class PureDecisionTests(unittest.TestCase):
    def test_48_paired_boolean_cost_combinations(self):
        for a,before,candidate,d in itertools.product((False,True),repeat=4):
            for costdelta in (-1,0,1):
                # Two independently scored dimensions, no summing away regressions.
                pairs=[(a,before),(candidate,d)]
                g=e.transitions([{'without-context':{'x':a},'with-context':{'x':before}}],'x')
                r=e.transitions([{'without-context':{'x':candidate},'with-context':{'x':d}}],'x')
                cost={'comparison':{'comparison_eligible':True,'change':{'candidate_minus_baseline':str(costdelta)}}}
                result=e.decision(g,r,cost,100)
                no_loss=all(not old or new for old,new in pairs)
                no_gain=all(old or not new for old,new in pairs)
                expected_candidate=no_loss and costdelta<=0 and (any(not old and new for old,new in pairs) or costdelta<0)
                expected_baseline=no_gain and costdelta>=0 and (any(old and not new for old,new in pairs) or costdelta>0)
                self.assertIs(result['candidate_dominates_observed_cases'],expected_candidate)
                self.assertIs(result['baseline_dominates_observed_cases'],expected_baseline)

    def test_empty_and_reduced_fractions(self):
        self.assertEqual(e.measure(0,25),{'count':0,'total':25,'rate':{'numerator':'0','denominator':'1'}})
        self.assertEqual(e.measure(10,25)['rate'],{'numerator':'2','denominator':'5'})
        self.assertIsNone(e.measure(0,0)['rate'])
        self.assertIsNone(e.fraction(None))


class ActualLoopback(unittest.TestCase):
    def test_http_receipts_to_quality_and_cost(self):
        with tempfile.TemporaryDirectory(prefix='qbrain-n48l-http-') as temp:
            root=Path(temp); p=plan(); key=make_key(p); rows={r['request_id']:r for r in p['rows']}; calls=[]
            class Handler(BaseHTTPRequestHandler):
                def log_message(self,*args): pass
                def do_POST(self):
                    body=c.decode(self.rfile.read(int(self.headers['Content-Length'])))
                    task=c.decode(body['messages'][1]['content'].encode())
                    row=rows[task['case_id']]
                    calls.append({'request_id':row['request_id'],'authorization_present':self.headers.get('Authorization') is not None})
                    value=response(row,50 if row['mode']=='with-context' else 100)
                    # Explicit synthetic reference responder, not a model or claimed independent inference.
                    value['choices'][0]['message']['content']=json.dumps(answer_for(key,row,'perfect'))
                    raw=c.encode(value); self.send_response(200); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            p['endpoint']=f'http://127.0.0.1:{server.server_port}/v1/chat/completions'; raw=c.encode(p)
            try:
                report=m.run(raw,root/'run',approved_sha=c.digest(raw),approved_endpoint=p['endpoint'],request_cap=100)
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=5)
            self.assertEqual(report['completed'],100)
            self.assertEqual(len(calls),100); self.assertTrue(all(not x['authorization_present'] for x in calls))
            kp=root/'evaluator-key.json'; kp.write_bytes(c.encode(key))
            rp=root/'rates.json'; rp.write_bytes(b.encode(price()))
            cmd=[sys.executable,str(Path(e.__file__)),'export','--run',str(root/'run'),'--key',str(kp),
                 '--rates',str(rp),'--binary',str(BINARY),'--output',str(root/'report')]
            completed=subprocess.run(cmd,capture_output=True,timeout=90)
            self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
            result=b.decode((root/'report/evaluation.json').read_bytes())
            self.assertEqual(result['decision']['result'],'CANDIDATE_DOMINATES_OBSERVED_CASES')
            self.assertEqual(result['execution_kind'],'LOOPBACK_TEST')
            self.assertFalse(result['quality_preserving_savings_verified'])
            self.assertEqual(result['arms']['with-context']['answerable_resolution']['count'],25)
            cmd[2]='verify'; verified=subprocess.run(cmd,capture_output=True,timeout=90)
            self.assertEqual(verified.returncode,0,verified.stdout+verified.stderr)
            if EVIDENCE:
                output=EVIDENCE/'loopback'; output.mkdir(parents=True,exist_ok=False)
                shutil.copytree(root/'run',output/'run'); shutil.copytree(root/'report',output/'report')
                shutil.copyfile(kp,output/'evaluator-key.SYNTHETIC.json'); shutil.copyfile(rp,output/'rates.json')
                (output/'export.stdout').write_bytes(completed.stdout); (output/'verify.stdout').write_bytes(verified.stdout)
                (output/'RESULT.json').write_bytes(b.encode({'schema':'qbrain-n48l-loopback-test-v1','requests':100,
                    'passed':True,'binary_sha256':b.sha(BINARY.read_bytes()),'execution_kind':'LOOPBACK_TEST',
                    'reference_responder_uses_synthetic_answers':True,'real_model_quality_verified':False}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--binary',type=Path,required=True); parser.add_argument('--evidence',type=Path)
    args, rest=parser.parse_known_args(); BINARY=args.binary.resolve(strict=True); EVIDENCE=args.evidence
    unittest.main(argv=[sys.argv[0],*rest],verbosity=2)
