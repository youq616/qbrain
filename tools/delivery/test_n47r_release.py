"""N47R verifier/publication regressions. Fake API and oracle fixtures only."""
import copy
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile

import publish_n47r as p
import verify_n47r_evidence as v
import test_reviewed_n47o as old_tests


def run_fixture(label):
    ident, source, path, names = p.RUNS[label]
    live = {'id': ident, 'head_sha': source, 'path': path, 'event': 'push', 'run_attempt': 1,
            'status': 'completed', 'conclusion': 'success', 'repository': {'full_name': p.REPO},
            'head_repository': {'full_name': p.REPO}}
    rows = []
    for name, jid in names.items():
        steps = (['Unchanged full native unit suite'] if name == 'full-native' else
                 ['Prepare independently pinned packages', 'Actual guide extraction and old-to-new upgrade']
                 if label == 'upgrade' else ['Fetch only the pinned public baseline',
                 'Test builder and reproduce the exact candidate twice', 'Actual extracted Windows installer and task gates'])
        rows.append({'id': jid, 'name': name, 'run_id': ident, 'head_sha': source, 'run_attempt': 1,
                     'status': 'completed', 'conclusion': 'success', 'steps': [
                         {'number': i, 'name': text, 'status': 'completed',
                          'conclusion': 'skipped' if name == 'bundle (ubuntu-latest)' and text.startswith('Actual extracted') else 'success'}
                         for i, text in enumerate(steps, 1)]})
    return live, {'jobs': rows, 'total_count': len(rows)}


def upgrade_fixture(shell):
    script = b'fixed script\r\n'
    result = {'schema': 'qbrain-n47r-upgrade-v1', 'result': 'PASS', 'source_commit': v.UPGRADE_SOURCE,
              'native_windows': True, 'shell_major': shell, 'real_client_verified': False, 'count': 37,
              'candidate_sha256': v.BUNDLE_SHA, 'baseline_sha256': p.BASE_SHA,
              'script_sha256': v.sha(script), 'checks': [{'name': x, 'passed': True} for x in v.upgrade_names()]}
    log = ''.join('PASS '+str(i)+' : '+name+'\n' for i, name in enumerate(v.upgrade_names(), 1)).encode()
    return result, log, script


class ReadbackTests(unittest.TestCase):
    def test_exact_crlf_accepts_legacy_non_utf8_but_no_other_transform(self):
        raw = b'legacy\x81\nline\n'; modes = {'old.txt': '100644'}
        self.assertEqual(v.windows_source_match({'old.txt': raw}, {'old.txt': raw.replace(b'\n', b'\r\n')}, modes, modes), 1)
        for bad in (raw + b'x', b'\xef\xbb\xbf'+raw, raw.replace(b'\n', b'\r\n', 1), raw.replace(b'line', b'other')):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError): v.windows_source_match({'old.txt': raw}, {'old.txt': bad}, modes, modes)

    def test_membership_and_modes_must_match(self):
        for observed, modes in (({}, {}), ({'a': b'x'}, {'a': '100755'}), ({'A': b'x'}, {'A': '100644'})):
            with self.assertRaises(ValueError): v.windows_source_match({'a': b'x'}, observed, {'a': '100644'}, modes)

    def test_unsafe_archives_duplicates_and_crc(self):
        def archive(entries):
            raw=io.BytesIO()
            with zipfile.ZipFile(raw,'w') as z:
                for name, data in entries: z.writestr(name,data)
            return raw.getvalue()
        for rows in ([('../bad',b'x')], [('A',b'x'),('a',b'y')], [('a',b'x'),('a/b',b'y')], [('a:b',b'y')]):
            with self.assertRaises(ValueError): v.unzip(archive(rows))
        raw = bytearray(archive([('a',b'crc-sentinel')]));raw[raw.index(b'crc-sentinel')] ^= 1
        with self.assertRaises(zipfile.BadZipFile): v.unzip(bytes(raw))

    def test_upgrade_exact_coverage_shell_scope_and_log(self):
        for shell in (5,7):
            args=upgrade_fixture(shell);self.assertEqual(v.upgrade_report(*args,shell)['checks'],37)
        for kind in ('source','shell','typed-shell','typed-count','scope','missing','duplicate','false','script','bundle','log'):
            with self.subTest(kind=kind):
                r,log,script=upgrade_fixture(5)
                if kind=='source':r['source_commit']='wrong'
                if kind=='shell':r['shell_major']=7
                if kind=='typed-shell':r['shell_major']=True
                if kind=='typed-count':r['count']=True
                if kind=='scope':r['real_client_verified']=True
                if kind=='missing':r['checks'].pop()
                if kind=='duplicate':r['checks'][-1]=r['checks'][0]
                if kind=='false':r['checks'][0]['passed']=False
                if kind=='script':r['script_sha256']='wrong'
                if kind=='bundle':r['candidate_sha256']='wrong'
                if kind=='log':log=log.replace(b'PASS 1 :',b'PASS 9 :')
                with self.assertRaises(ValueError):v.upgrade_report(r,log,script,5)

    def test_native_pins_reject_missing_source_and_run_before_loading_code(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for pins in ({}, {'source_commit':v.SOURCE,'source_tree':v.TREE,'run_id':v.RUN,'artifacts':{}},
                         {'source_commit':v.SOURCE,'source_tree':v.TREE,'run_id':True,'artifacts':{}}):
                with self.assertRaises(ValueError):v.verify(root,pins,root/'absent.zip')

    def test_live_jobs_validate_exact_pinned_attempt_and_mandatory_steps(self):
        for label in p.RUNS:p.validate_live(label,*run_fixture(label))
        for kind in ('source','attempt','event','repo','status','truncate','duplicate','failed','job-source','skip-native','missing-step'):
            with self.subTest(kind=kind):
                live,listing=run_fixture('native');job=listing['jobs'][0]
                if kind=='source':live['head_sha']='wrong'
                if kind=='attempt':live['run_attempt']=2
                if kind=='event':live['event']='pull_request'
                if kind=='repo':live['head_repository']={'full_name':'other/repo'}
                if kind=='status':live['conclusion']='failure'
                if kind=='truncate':listing['jobs'].pop()
                if kind=='duplicate':listing['jobs'][-1]=copy.deepcopy(job)
                if kind=='failed':job['conclusion']='failure'
                if kind=='job-source':job['head_sha']='wrong'
                if kind=='skip-native':job['steps'][0]['conclusion']='skipped'
                if kind=='missing-step':job['steps'][0]['name']='dummy successful step'
                with self.assertRaises(ValueError):p.validate_live('native',live,listing)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.h=p.legacy_helpers()
        self.rebind=patch.object(old_tests,'p',self.h);self.rebind.start();self.addCleanup(self.rebind.stop)
        self.assets={'product.zip':b'fixture product','guide.md':b'fixture guide'}
        for name,raw in self.assets.items():(self.root/name).write_bytes(raw)

    def test_new_description_and_same_id_verified_twice(self):
        api=old_tests.FakeGitHub();r=p.publish(api,self.assets,self.root,self.h)
        self.assertEqual(api.downloads,4);self.assertEqual(api.patches,1)
        self.assertEqual(r['tag'],p.TAG);self.assertIs(r['repackaged'],True);self.assertIs(r['exe_recompiled'],False)
        body=next(body for method,url,body in api.calls if method=='POST' and url=='releases')
        self.assertIn('ZIP 重新组装',body['body']);self.assertEqual(body['target_commitish'],v.SOURCE)
        self.assertEqual(body['make_latest'],'false')

    def test_all_prepublication_state_failures_leave_unpublished(self):
        for fault in ('existing','draft-page-two','listing-error','wrong-tag','no-digest','wrong-size','not-uploaded',
                      'duplicate-id','extra-asset','bad-bytes','replace-after-download','tag-change','upload-interrupted','bad-draft'):
            with self.subTest(fault=fault):
                api=old_tests.FakeGitHub(fault)
                with self.assertRaises((ValueError,RuntimeError)):p.publish(api,self.assets,self.root,self.h)
                self.assertEqual(api.patches,0);self.assertFalse(any(x[0]=='DELETE' for x in api.calls))

    def test_public_replacement_and_latest_are_not_silent_success(self):
        for fault in ('replace-public','wrong-public','latest'):
            api=old_tests.FakeGitHub(fault)
            with self.assertRaises(ValueError):p.publish(api,self.assets,self.root,self.h)
            self.assertEqual(api.patches,1)

    def test_modified_local_asset_rejected(self):
        (self.root/'product.zip').write_bytes(b'changed');api=old_tests.FakeGitHub()
        with self.assertRaises(ValueError):p.publish(api,self.assets,self.root,self.h)
        self.assertEqual(api.patches,0)

    def test_anonymous_readback_success_tamper_and_missing_publication(self):
        receipt={'result':'PUBLISHED','release_id':999}
        def urlopen(url,**kwargs):
            self.assertIsInstance(url,str);self.assertNotIn('token',url)
            return io.BytesIO(self.assets[url.rsplit('/',1)[-1]])
        with patch.object(p,'urlopen',side_effect=urlopen):
            self.assertIs(p.anonymous_readback(self.assets,receipt,self.root)['authenticated'],False)
        with patch.object(p,'urlopen',return_value=io.BytesIO(b'wrong')):
            with self.assertRaises(ValueError):p.anonymous_readback(self.assets,receipt,self.root)
        with self.assertRaises(ValueError):p.anonymous_readback(self.assets,{'result':'VERIFIED'},self.root)


if __name__=='__main__':unittest.main(verbosity=2)
