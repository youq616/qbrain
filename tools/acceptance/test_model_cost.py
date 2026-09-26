"""N48J tests with actual native accounting and synthetic N47S execution records.
The fast fixture replaces ONLY HTTP post, not receipts, bridge or native pricing.
A separate real loopback test exercises the unmodified HTTP executor end-to-end.
"""
from __future__ import annotations
import argparse
import copy
from fractions import Fraction
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
from test_memory_tasks import fixture

BINARY = None
EVIDENCE = None


def price():
    return {'schema': 'qbrain-model-cost-rates-v1', 'scope': b.SCOPE, 'currency': 'USD', 'rates': [
        {'rate_id': 'main-price', 'provider': 'openai', 'model': 'fixture-model', 'per_million':
         {'input_uncached': '1.234567', 'input_cache_read': '0.123456', 'input_cache_write': '2.000003', 'output': '3.456789'}}]}


def plan():
    p = {'schema': 'qbrain-model-plan-v2', 'context_projection': m.CONTEXT_PROJECTION, 'plan_id': 'd'*32,
         'run_id': 'a'*32, 'endpoint': 'http://127.0.0.1:19481/v1/chat/completions', 'loopback_test': True,
         'model': 'fixture-model', 'max_completion_tokens': 512, 'token_field': 'max_completion_tokens',
         'timeout_seconds': 10, 'packet_text': {}}
    for mode in m.MODES:
        _, raw, _ = fixture(mode)
        p['packet_text'][mode] = raw.decode()
    p['rows'] = m.schedule(p['plan_id'])
    return p


def response(row, n=100):
    answer = {'case_id': row['request_id'], 'state': 'unknown', 'values': [], 'fact_ids': []}
    return {'id': 'response-' + row['request_id'], 'model': 'fixture-model', 'object': 'chat.completion',
            'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': json.dumps(answer)}}],
            'usage': {'prompt_tokens': n, 'completion_tokens': 20, 'total_tokens': n + 20,
                      'prompt_tokens_details': {'cached_tokens': 20, 'cache_write_tokens': 0}}}


def make_run(root: Path, mutate=None, at=16):
    p = plan(); i = 0
    def post(plan, body, key):
        nonlocal i
        row = p['rows'][i]; i += 1
        obj = response(row, 100 if row['mode'] == 'without-context' else 50)
        if mutate is not None and (at is None or i == at):
            obj = mutate(obj, i)
        if isinstance(obj, tuple):
            return obj
        return 200, c.encode(obj)
    raw = c.encode(p)
    with patch.object(m, 'post', side_effect=post):
        r = m.run(raw, root, approved_sha=c.digest(raw), approved_endpoint=p['endpoint'], request_cap=m.COUNT)
    return r


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = tempfile.TemporaryDirectory(prefix='qbrain-model-cost-template-')
        cls.source = Path(cls.template.name)/'run'
        make_run(cls.source)

    @classmethod
    def tearDownClass(cls):
        cls.template.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='qbrain-model-cost-tests-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root/'run'
        shutil.copytree(self.source, self.run)
        self.rates = self.root/'prices.json'
        self.rates.write_bytes(b.encode(price()))
        self.output = self.root/'out'

    def analysis(self):
        return b.analyze(self.run, self.rates, BINARY)[0]

    def remake(self, mutate=None, at=16):
        shutil.rmtree(self.run)
        return make_run(self.run, mutate, at)

    def patch_json(self, name, fn):
        p = self.run/name
        obj = c.decode(p.read_bytes()); fn(obj); p.write_bytes(c.encode(obj))

    def edit_row(self, fn, index=0):
        report = c.decode((self.run/'run.json').read_bytes())
        fn(report['rows'][index]); (self.run/'run.json').write_bytes(c.encode(report))
        (self.run/f'{index+1:03}'/'receipt.json').write_bytes(c.encode(report['rows'][index]))

    def test_01_complete_costs_raw_cache_and_exact_ratio(self):
        r = self.analysis()
        self.assertEqual((r['attempted_requests'], r['completed_responses'], r['unattempted_requests']), (100, 100, 0))
        self.assertTrue(r['comparison']['comparison_eligible'])
        self.assertEqual(r['cost_scope'], b.SCOPE)
        totals = {}
        for mode, inp in (('without-context', 100), ('with-context', 50)):
            total = 50 * (Fraction('1.234567') * (inp-20) + Fraction('0.123456') * 20 + Fraction('3.456789') * 20)/10**6
            ledger = r['ledgers'][mode]
            self.assertEqual(Fraction(ledger['cost_report']['summary']['total_estimate']), total)
            self.assertEqual(len(ledger['cost_input']['calls']), 50)
            self.assertEqual(ledger['cost_input']['calls'][0]['tokens']['input_cache_read'], 20)
            totals[mode] = total
        change = r['comparison']['change']
        difference = totals['with-context'] - totals['without-context']
        self.assertEqual(Fraction(change['candidate_minus_baseline']), difference)
        self.assertEqual(Fraction(int(change['relative_change']['numerator']), int(change['relative_change']['denominator'])), difference/totals['without-context'])
        self.assertFalse(r['full_pipeline_costs_included'])
        self.assertFalse(r['quality_verified'])
        # Raw prompt/answer/user endpoint never exported, not even a redacted copy.
        _, outputs = b.analyze(self.run, self.rates, BINARY)
        serialized = b''.join(outputs.values())
        for forbidden in (b'messages', b'finish_reason', b'19481', b'packet_text', c.INSTRUCTIONS.encode()):
            self.assertNotIn(forbidden, serialized)

    def test_02_export_verify_is_deterministic_and_no_overwrite(self):
        result = b.execute(self.run, self.rates, BINARY, self.output)
        self.assertEqual(result['result'], 'EXPORTED')
        self.assertEqual(b.execute(self.run, self.rates, BINARY, self.output, True)['result'], 'VERIFIED')
        before = {p.name:p.read_bytes() for p in self.output.iterdir()}
        with self.assertRaisesRegex(b.Reject, 'output_exists'):
            b.execute(self.run, self.rates, BINARY, self.output)
        self.assertEqual(before, {p.name:p.read_bytes() for p in self.output.iterdir()})

    def test_03_no_key_or_network_or_scorer(self):
        with patch.object(m, 'post', side_effect=AssertionError('HTTP forbidden')), \
             patch.object(m, 'score_run', side_effect=AssertionError('score forbidden')), \
             patch.object(socket, 'create_connection', side_effect=AssertionError('network forbidden')), \
             patch.dict(os.environ, {'QBRAIN_EVAL_KEY':'DO-NOT-READ-OR-COPY-SECRET'}):
            r, files = b.analyze(self.run, self.rates, BINARY)
        self.assertEqual(r['provider_requests_sent_by_bridge'], 0)
        self.assertNotIn(b'DO-NOT-READ-OR-COPY-SECRET', b''.join(files.values()))

    def test_04_missing_usage_or_cache_never_inferred(self):
        mutations = [lambda v,i: {k:x for k,x in v.items() if k != 'usage'},
                     lambda v,i: {**v,'usage':{k:x for k,x in v['usage'].items() if k != 'prompt_tokens_details'}},
                     lambda v,i: {**v,'usage':{**v['usage'],'prompt_tokens_details': {'cached_tokens':None,'cache_write_tokens':0}}}]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.remake(mutate); r = self.analysis()
                self.assertEqual(r['completed_responses'], 100)
                self.assertFalse(r['comparison']['comparison_eligible'])
                self.assertIsNone(r['comparison']['change']['candidate_minus_baseline'])
                self.assertIn('cost_components_unknown', r['comparison']['unavailable_reasons'])

    def test_05_unpriced_model_and_price_drift(self):
        p = price(); p['rates'] = []; self.rates.write_bytes(b.encode(p))
        r = self.analysis()
        self.assertFalse(r['comparison']['comparison_eligible'])
        self.assertIn('primary_model_unknown_or_multiple', r['comparison']['unavailable_reasons'])
        self.rates.write_bytes(b.encode(price()))
        self.remake(lambda v,i: {**v, 'model':'model-snapshot-other'})
        r = self.analysis()
        self.assertFalse(r['comparison']['comparison_eligible'])
        p=price(); second=copy.deepcopy(p['rates'][0]); second.update(model='model-snapshot-other', rate_id='other')
        p['rates'].append(second); self.rates.write_bytes(b.encode(p))
        r=self.analysis()
        self.assertFalse(r['comparison']['comparison_eligible'])
        self.assertIn('primary_model_unknown_or_multiple',r['comparison']['unavailable_reasons'])

    def test_06_terminal_failed_answer_usage_is_not_dropped(self):
        def wrong(v,i):
            v['choices'][0]['message']['content']='{"case_id":"wrong"}'; return v
        self.remake(wrong)
        r=self.analysis(); self.assertEqual((r['attempted_requests'],r['completed_responses']),(16,15))
        self.assertIsNone(r['comparison']); self.assertEqual(r['unattempted_requests'],84)
        self.assertEqual(sum(len(x['cost_input']['calls']) for x in r['ledgers'].values()),16)
        failed=[call for x in r['ledgers'].values() for call in x['cost_input']['calls'] if call['outcome']=='failure']
        self.assertEqual(len(failed),1); self.assertEqual(failed[0]['tokens']['output'],20)
        self.assertEqual(r['observations'][15]['normalization'],'terminal_response_projection')
        self.assertIsNone(r['observations'][16]['call_id'])

    def test_07_failure_classes_and_nonterminal_unknown(self):
        def transport(v,i): raise m.TransferError('network_error')
        def interrupt(v,i): raise KeyboardInterrupt()
        def nonterminal(v,i): v['choices'][0]['finish_reason']=None; return v
        faults=[('http_error',lambda v,i:(429,b'')),('invalid_json',lambda v,i:(200,b'bad JSON')),
                ('transport_error',transport),('interrupted',interrupt),('invalid_response',nonterminal)]
        for status, fn in faults:
            with self.subTest(status=status):
                self.remake(fn); r=self.analysis()
                self.assertEqual(r['observations'][15]['status'],status)
                self.assertIsNone(r['comparison'])
                failed=[call for x in r['ledgers'].values() for call in x['cost_input']['calls'] if call['outcome']=='failure']
                self.assertEqual(len(failed),1)
                self.assertTrue(all(x is None for x in failed[0]['tokens'].values()))

    def test_08_credential_echo_remains_unknown_and_private(self):
        self.remake(lambda v,i:(200,b'not-json'))
        self.edit_row(lambda row: row.update(status='credential_echo'),15)
        r=self.analysis(); self.assertEqual(r['observations'][15]['normalization'],'unknown_failed_attempt')
        self.assertIsNone(r['comparison'])

    def test_09_last_failure_keeps_fifty_task_manifest_but_no_deltas(self):
        def wrong(v,i): v['choices'][0]['message']['content']='{}'; return v
        self.remake(wrong,100); r=self.analysis()
        self.assertEqual(r['attempted_requests'],100); self.assertEqual(r['completed_responses'],99)
        self.assertIsNotNone(r['comparison']); self.assertFalse(r['comparison']['comparison_eligible'])
        self.assertIn('declared_coverage_incomplete',r['comparison']['unavailable_reasons'])
        self.assertEqual(len(r['comparison']['by_task']),50)
        self.assertTrue(all(t['change']['candidate_minus_baseline'] is None for t in r['comparison']['by_task']))

    def test_10_native_rejects_contradictory_or_unsupported_usage(self):
        for fn in (lambda v,i:{**v,'usage':{**v['usage'],'prompt_tokens_details':{'cached_tokens':999,'cache_write_tokens':0}}},
                   lambda v,i:{**v,'usage':{**v['usage'],'prompt_tokens_details':{'cached_tokens':True,'cache_write_tokens':0}}},
                   lambda v,i:{**v,'usage':{**v['usage'],'extra':'unsupported'}}):
            self.remake(fn)
            with self.assertRaisesRegex(b.Reject,'model_cost_native_usage_'):
                self.analysis()
            self.assertFalse(self.output.exists())

    def test_11_duplicate_cross_arm_identity_rejected(self):
        self.remake(lambda v,i:{**v,'id':'duplicate-id'},at=None)
        with self.assertRaisesRegex(b.Reject,'duplicate_response'): self.analysis()

    def test_12_no_invented_provider_kind(self):
        self.remake(lambda v,i:{k:x for k,x in v.items() if k!='object'})
        with self.assertRaisesRegex(b.Reject,'unsupported_response'): self.analysis()

    def test_13_source_file_tampering(self):
        for name in ('plan.json','run.json','001/receipt.json','001/started.json','001/request.json','001/response.bin'):
            p=self.run/name; old=p.read_bytes(); p.write_bytes(b'{}')
            with self.subTest(name=name):
                with self.assertRaises((b.Reject,ValueError,KeyError,TypeError)): self.analysis()
            p.write_bytes(old)
        self.assertEqual(self.analysis()['completed_responses'],100)

    def test_14_strict_receipt_type_checks_even_when_both_copies_changed(self):
        cases=[lambda row:row.update(index=True),lambda row:row.update(http_status=200.0),
               lambda row:row.update(response_received_bytes=True),lambda row:row.update(elapsed_ms=False),
               lambda row:row.update(elapsed_ms=-1),lambda row:row.update(extra=1),
               lambda row:row.update(usage={'input_tokens':True,'output_tokens':20})]
        for fn in cases:
            runraw=(self.run/'run.json').read_bytes(); rowraw=(self.run/'001/receipt.json').read_bytes()
            self.edit_row(fn)
            with self.subTest(fn=fn):
                with self.assertRaises((b.Reject,ValueError,TypeError)): self.analysis()
            (self.run/'run.json').write_bytes(runraw); (self.run/'001/receipt.json').write_bytes(rowraw)

    def test_15_run_count_flags_and_continuation(self):
        raw=(self.run/'run.json').read_bytes()
        changes=[lambda v:v.update(attempted=True),lambda v:v.update(completed=99),lambda v:v.update(planned=100.0),
                 lambda v:v.update(host_consumption_verified=True),lambda v:v.update(result='INCOMPLETE'),
                 lambda v:v['rows'].reverse(),lambda v:v['rows'].pop()]
        for fn in changes:
            self.patch_json('run.json',fn)
            with self.assertRaises((b.Reject,ValueError,TypeError)): self.analysis()
            (self.run/'run.json').write_bytes(raw)

    def test_16_source_inventory_and_crash(self):
        (self.run/'EXTRA.txt').write_text('not accepted')
        with self.assertRaisesRegex(b.Reject,'inventory'): self.analysis()
        (self.run/'EXTRA.txt').unlink(); (self.run/'001/extra').write_bytes(b'{}')
        with self.assertRaisesRegex(b.Reject,'inventory'): self.analysis()
        (self.run/'001/extra').unlink(); (self.run/'run.json').unlink()
        with self.assertRaises(OSError): self.analysis()

    def test_17_json_duplicate_nonfinite_depth_and_encoding(self):
        p=self.run/'run.json'; old=p.read_bytes()
        for raw in (b'{"schema":1,"schema":2}', b'{"x":NaN}', b'{"x":1e999}', b'{"x":"\\ud800"}',
                    b'['*50+b'0'+b']'*50,b'{"x":"\xff"}'):
            p.write_bytes(raw)
            with self.subTest(raw=raw):
                with self.assertRaises((b.Reject,ValueError)): self.analysis()
        p.write_bytes(old)

    def test_18_price_scope_ambiguity_and_rejections(self):
        cases=[]
        p=price(); p['scope']='all_pipeline'; cases.append(p)
        p=price(); p['rates'].append(copy.deepcopy(p['rates'][0])); p['rates'][1]['rate_id']='same-model-other-price'; cases.append(p)
        p=price(); p['rates'][0]['provider']='anthropic'; cases.append(p)
        p=price(); p['rates'][0]['per_million']['output']=True; cases.append(p)
        p=price(); p['rates'][0]['rate_id']='n48j-unpriced-reserved'; cases.append(p)
        p=price(); p['extra']='no'; cases.append(p)
        for p in cases:
            self.rates.write_bytes(b.encode(p))
            with self.assertRaises((b.Reject,ValueError)): self.analysis()

    def test_19_no_output_inside_source(self):
        with self.assertRaisesRegex(b.Reject,'output_inside_source'):
            b.execute(self.run,self.rates,BINARY,self.run/'out')
        self.assertFalse((self.run/'out').exists())

    def test_20_symlink_regular_file_and_parent(self):
        target=self.run/'001/request.json'; original=target.read_bytes(); outside=self.root/'outside'; outside.write_bytes(original)
        target.unlink()
        try: target.symlink_to(outside)
        except OSError as e:
            target.write_bytes(original); self.skipTest('Symlink creation unavailable: '+type(e).__name__)
        with self.assertRaisesRegex(b.Reject,'link_input'): self.analysis()
        target.unlink(); target.write_bytes(original)
        link=self.root/'linked-root'; link.symlink_to(self.run,target_is_directory=True)
        with self.assertRaisesRegex(b.Reject,'link_input'): b.analyze(link,self.rates,BINARY)

    def test_21_source_mutation_before_publish(self):
        original=b.Native.recheck
        def changing(native):
            original(native)
            self.patch_json('run.json',lambda v:v.update(attempted=99))
        # Change during native work, before the snapshot recheck, not after it.
        old=b.Native.invoke
        changed=False
        def invoke(native,*args):
            nonlocal changed
            v=old(native,*args)
            if not changed:
                changed=True; self.patch_json('run.json',lambda value:value.update(attempted=99))
            return v
        with patch.object(b.Native,'invoke',invoke):
            with self.assertRaises(b.Reject): b.execute(self.run,self.rates,BINARY,self.output)
        self.assertFalse(self.output.exists())

    def test_22_readback_rejects_rehashed_cost_scope_and_inventory(self):
        b.execute(self.run,self.rates,BINARY,self.output)
        original={p.name:p.read_bytes() for p in self.output.iterdir()}
        for mutation in ('cost','scope','bool','duplicate','missing','extra','manifest'):
            for p in self.output.iterdir(): p.unlink()
            for name,raw in original.items(): (self.output/name).write_bytes(raw)
            analysis=c.decode(original['analysis.json'])
            if mutation=='cost': analysis['comparison']['change']['candidate_minus_baseline']='0.000000000000'
            if mutation=='scope': analysis['full_pipeline_costs_included']=True
            if mutation=='bool': analysis['attempted_requests']=True
            if mutation in ('cost','scope','bool'):
                new=b.encode(analysis); (self.output/'analysis.json').write_bytes(new)
                manifest=c.decode(original['MANIFEST.json']); manifest['files']['analysis.json']={'bytes':len(new),'sha256':b.sha(new)}
                (self.output/'MANIFEST.json').write_bytes(b.encode(manifest))
            if mutation=='duplicate': (self.output/'analysis.json').write_bytes(b'{"schema":"bad",'+original['analysis.json'][1:])
            if mutation=='missing': (self.output/'comparison-input.json').unlink()
            if mutation=='extra': (self.output/'extra').write_bytes(b'{}')
            if mutation=='manifest': (self.output/'MANIFEST.json').write_bytes(b'{}')
            with self.subTest(mutation=mutation):
                with self.assertRaises(b.Reject): b.execute(self.run,self.rates,BINARY,self.output,True)

    def test_23_cli_exit_and_body_free_errors(self):
        command=[sys.executable,str(Path(b.__file__)),'export','--run',str(self.run),'--rates',str(self.rates),
                 '--binary',str(BINARY),'--output',str(self.output)]
        p=subprocess.run(command,capture_output=True,timeout=90)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr); self.assertEqual(p.stderr,b'')
        p=subprocess.run(command,capture_output=True,timeout=90)
        self.assertEqual(p.returncode,2); self.assertEqual(p.stderr,b'')
        self.assertNotIn(str(self.root).encode(),p.stdout)
        self.assertEqual(b.decode(p.stdout),{'error':{'code':'model_cost_output_exists'}})

    def test_24_native_action_oracle_failure_no_bundle(self):
        with patch.object(b.Native,'invoke',side_effect=b.Reject('model_cost_native_cost_overflow')):
            with self.assertRaises(b.Reject): b.execute(self.run,self.rates,BINARY,self.output)
        self.assertFalse(self.output.exists())

    def test_25_first_failure_has_no_synthetic_missing_calls(self):
        self.remake(lambda v,i:(503,b''),1)
        r=self.analysis(); self.assertEqual(r['attempted_requests'],1)
        counts=sorted(ledger['cost_report']['summary']['calls'] for ledger in r['ledgers'].values())
        self.assertEqual(counts,[0,1]); self.assertIsNone(r['comparison'])
        self.assertEqual(sum(o['call_id'] is None for o in r['observations']),99)

    def test_26_size_limits_reject_before_publication(self):
        p=self.run/'001/receipt.json'; p.write_bytes(b' ' * 65537)
        with self.assertRaisesRegex(b.Reject,'file_limit'): b.execute(self.run,self.rates,BINARY,self.output)
        self.assertFalse(self.output.exists())


class LoopbackPipeline(unittest.TestCase):
    def test_real_http_execution_to_native_cost_comparison(self):
        temp=tempfile.TemporaryDirectory(prefix='qbrain-n48j-http-'); self.addCleanup(temp.cleanup)
        root=Path(temp.name); p=plan(); rows={row['request_id']:row for row in p['rows']}; calls=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                body=c.decode(self.rfile.read(int(self.headers['Content-Length'])))
                task=c.decode(body['messages'][1]['content'].encode()); row=rows[task['case_id']]
                calls.append({'request_id':row['request_id'],'auth':self.headers.get('Authorization')})
                value=response(row,100 if row['mode']=='without-context' else 50)
                data=c.encode(value); self.send_response(200); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler); thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        p['endpoint']=f'http://127.0.0.1:{server.server_port}/v1/chat/completions'; raw=c.encode(p)
        try:
            result=m.run(raw,root/'run',approved_sha=c.digest(raw),approved_endpoint=p['endpoint'],request_cap=100)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
        self.assertEqual(result['completed'],100); self.assertEqual(len(calls),100)
        self.assertTrue(all(row['auth'] is None for row in calls))
        rates=root/'rates.json'; rates.write_bytes(b.encode(price()))
        command=[sys.executable,str(Path(b.__file__)),'export','--run',str(root/'run'),'--rates',str(rates),
                 '--binary',str(BINARY),'--output',str(root/'report')]
        child=subprocess.run(command,capture_output=True,timeout=90)
        self.assertEqual(child.returncode,0,child.stdout+child.stderr)
        report=c.decode((root/'report/analysis.json').read_bytes())
        self.assertEqual(report['execution_kind'],'LOOPBACK_TEST'); self.assertTrue(report['comparison']['comparison_eligible'])
        self.assertEqual(Fraction(report['comparison']['change']['candidate_minus_baseline']),-50*50*Fraction('1.234567')/10**6)
        self.assertEqual(b.execute(root/'run',rates,BINARY,root/'report',True)['result'],'VERIFIED')
        if EVIDENCE:
            dest=EVIDENCE/'loopback-pipeline'; dest.mkdir(parents=True,exist_ok=False)
            shutil.copytree(root/'run',dest/'run'); shutil.copytree(root/'report',dest/'report'); shutil.copyfile(rates,dest/'rates.json')
            (dest/'execution.stdout').write_bytes(child.stdout)
            (dest/'RESULT.json').write_bytes(b.encode({'schema':'qbrain-n48j-loopback-v1','http_requests':len(calls),
                'completed':100,'execution_kind':'LOOPBACK_TEST','cost_scope':b.SCOPE,'passed':True,
                'binary_sha256':b.sha(BINARY.read_bytes()),'real_model_quality_verified':False}))


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--binary',type=Path,required=True); p.add_argument('--evidence',type=Path)
    args, rest=p.parse_known_args(); BINARY=args.binary.resolve(strict=True); EVIDENCE=args.evidence
    unittest.main(argv=[sys.argv[0],*rest],verbosity=2)
