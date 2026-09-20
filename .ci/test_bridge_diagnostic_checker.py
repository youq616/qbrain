import copy
import unittest
import check_bridge_diagnostics as c


def fixture():
    ds=[]
    phases=('complete','start','input','process','output','output')
    for code,phase in zip(c.CODES,phases):
        started=code!='start_failed'; done=code in ('completed','output_timeout','transport_error')
        d=dict(schema='qbrain-transport-diagnostic-v1',code=code,phase=phase,timeout_ms=10000,elapsed_ms=100,
            stage_ms=dict(start=2,input=3,process=5,output=90),wait_budget_ms=dict(input=9998,process=9995,output=9990),
            process_started=started,input_closed=started,process_exited=(True if done else False) if started else None,
            exit_code=(7 if code=='completed' else 0) if done else None,input_state='completed' if started else 'not_started',
            stdout_state='completed' if code=='completed' else 'running',stderr_state='completed' if code=='completed' else 'running',
            observation='before_cleanup',host_consumption_verified=False)
        ds.append(d)
    return dict(schema='qbrain-n47w-bridge-test-v1',result='PASS',source_commit='a'*40,shell_major=5,
        bridge_sha256=c.digest(b'bridge'),prior_bridge_sha256=c.digest(b'prior'),test_sha256=c.digest(b'test'),child_sha256=c.digest(b'child'),
        checks=[dict(name=n,passed=True) for n in c.NAMES],diagnostics=ds,failure='',real_client_verified=False)


def check(r):return c.validate(r,b'bridge',b'prior',b'test',b'child','a'*40,5)


class Checker(unittest.TestCase):
    def test_valid_scope(self):
        self.assertEqual(check(fixture())['checks'],29)
        self.assertIs(check(fixture())['real_client_verified'],False)
    def test_report_mutations(self):
        for kind in ('missing','duplicate','false','source','shell','hash','failure','scope','extra','diagnostic-order'):
            with self.subTest(kind=kind):
                r=fixture()
                if kind=='missing':r['checks'].pop()
                if kind=='duplicate':r['checks'][-1]=r['checks'][0]
                if kind=='false':r['checks'][0]['passed']=False
                if kind=='source':r['source_commit']='b'*40
                if kind=='shell':r['shell_major']=True
                if kind=='hash':r['bridge_sha256']='bad'
                if kind=='failure':r['failure']='fixture failed'
                if kind=='scope':r['real_client_verified']=True
                if kind=='extra':r['secret']='never permitted'
                if kind=='diagnostic-order':r['diagnostics'].reverse()
                with self.assertRaises(ValueError):check(r)
    def test_diagnostic_mutations(self):
        for key,value in (('arguments','private'),('phase','wrong'),('timeout_ms',True),('elapsed_ms',-1),
                          ('process_exited',1),('exit_code',False),('host_consumption_verified',True),
                          ('input_state','invented'),('code','raw exception')):
            d=fixture()['diagnostics'][0];d[key]=value
            with self.subTest(key=key):
                with self.assertRaises(ValueError):c.diagnostic(d)
        d=fixture()['diagnostics'][0];d['wait_budget_ms']['input']=10000
        with self.assertRaises(ValueError):c.diagnostic(d)
        d=fixture()['diagnostics'][0];d['wait_budget_ms']['output']=9999
        with self.assertRaises(ValueError):c.diagnostic(d)
    def test_json_rejects_duplicates_nonfinite_and_size(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":NaN}',b'\xff',b' '*262145):
            with self.subTest(raw=raw[:16]):
                with self.assertRaises(ValueError):c.decode(raw)


if __name__=='__main__':unittest.main(verbosity=2)
