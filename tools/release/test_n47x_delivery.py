"""Publication fixtures are mock API calls, never real releases or model results."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import n47x_publish as p
import n47x_verify as v


def fixture():
    run={'id':v.RUN,'head_sha':v.DELIVERY,'path':'.github/workflows/n47x-validation.yml','event':'push',
        'run_attempt':1,'status':'completed','conclusion':'success','repository':{'full_name':p.REPO},'head_repository':{'full_name':p.REPO}}
    jobs=[]
    for name,ident in p.JOBS.items():
        jobs.append({'id':ident,'name':name,'run_id':v.RUN,'head_sha':v.DELIVERY,'run_attempt':1,'status':'completed','conclusion':'success',
            'steps':[{'number':i,'name':step,'status':'completed','conclusion':'success'} for i,step in enumerate(sorted(p.REQUIRED[name]),1)]})
    return run,{'total_count':len(jobs),'jobs':jobs}


class Gates(unittest.TestCase):
    def test_live_success(self):p.validate_live(*fixture())
    def test_wrong_run_source_attempt_and_job_steps(self):
        for fault in ('run','source','attempt','event','repo','failed','missing','duplicate','step','skip','job-source'):
            with self.subTest(fault=fault):
                r,j=fixture()
                if fault=='run':r['id']+=1
                if fault=='source':r['head_sha']='other'
                if fault=='attempt':r['run_attempt']=True
                if fault=='event':r['event']='pull_request'
                if fault=='repo':r['repository']['full_name']='other/repo'
                if fault=='failed':r['conclusion']='failure'
                if fault=='missing':j['jobs'].pop()
                if fault=='duplicate':j['jobs'][1]=j['jobs'][0]
                if fault=='step':j['jobs'][0]['steps'][0]['name']='dummy'
                if fault=='skip':j['jobs'][0]['steps'][0]['conclusion']='skipped'
                if fault=='job-source':j['jobs'][0]['head_sha']='other'
                with self.assertRaises(ValueError):p.validate_live(r,j)
    def test_bad_archive_is_rejected_before_loading_its_code(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'source.zip').write_bytes(b'not a zip')
            with self.assertRaises(ValueError):v.verify(root)
    def test_upgrade_refuses_wrong_scope_and_types(self):
        for value in ({},None,{'schema':'qbrain-n47x-upgrade-v1','result':'PASS'}):
            with self.assertRaises(ValueError):v.upgrade(value,b'',b'',5)


class Publication(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.out=Path(self.temp.name)
        self.h=p.state_helpers()
        import test_reviewed_n47o as old
        self.old=old;self.patch=patch.object(old,'p',self.h);self.patch.start();self.addCleanup(self.patch.stop)
        self.assets={'product.zip':b'product','guide.md':b'guide'}
        for n,b in self.assets.items():(self.out/n).write_bytes(b)
    def test_publish_same_asset_ids_before_and_after_visibility(self):
        api=self.old.FakeGitHub();r=p.publish(api,self.assets,self.out,self.h)
        self.assertEqual(api.downloads,4);self.assertEqual(api.patches,1);self.assertIs(r['new_product_build'],True)
        body=next(b for m,url,b in api.calls if m=='POST' and url=='releases')
        self.assertEqual(body['target_commitish'],v.PRODUCT_SOURCE);self.assertIn('重新编译',body['body']);self.assertEqual(body['make_latest'],'false')
    def test_prepublication_failures_never_publish_or_delete(self):
        for fault in ('existing','draft-page-two','listing-error','wrong-tag','no-digest','wrong-size','not-uploaded','duplicate-id',
                'extra-asset','bad-bytes','replace-after-download','tag-change','upload-interrupted','bad-draft'):
            with self.subTest(fault=fault):
                api=self.old.FakeGitHub(fault)
                with self.assertRaises((ValueError,RuntimeError)):p.publish(api,self.assets,self.out,self.h)
                self.assertEqual(api.patches,0);self.assertFalse(any(x[0]=='DELETE' for x in api.calls))
    def test_public_change_is_not_reported_success(self):
        for fault in ('replace-public','wrong-public','latest'):
            api=self.old.FakeGitHub(fault)
            with self.assertRaises(ValueError):p.publish(api,self.assets,self.out,self.h)
            self.assertEqual(api.patches,1)
    def test_local_file_change_is_rejected(self):
        (self.out/'product.zip').write_bytes(b'changed');api=self.old.FakeGitHub()
        with self.assertRaises(ValueError):p.publish(api,self.assets,self.out,self.h)
        self.assertEqual(api.patches,0)
    def test_anonymous_download_checks_every_byte(self):
        def opened(url,**kwargs):return io.BytesIO(self.assets[url.rsplit('/',1)[-1]])
        receipt={'result':'PUBLISHED','release_id':1}
        with patch.object(p,'urlopen',side_effect=opened):
            self.assertFalse(p.public_readback(self.assets,receipt,self.out)['authenticated'])
        with patch.object(p,'urlopen',return_value=io.BytesIO(b'wrong')):
            with self.assertRaises(ValueError):p.public_readback(self.assets,receipt,self.out)
    def test_no_anonymous_read_before_publication(self):
        with patch.object(p,'urlopen') as fetch:
            with self.assertRaises(ValueError):p.public_readback(self.assets,{},self.out)
            fetch.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
