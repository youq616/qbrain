"""Read-only final N47L pin binding, using captured GitHub GET facts and committed Git blobs."""
import argparse,ast,hashlib,io,json,os,re,subprocess,sys,zipfile
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
for name in ('repo','template','workflow','pins','github-facts','package-artifact','report'):parser.add_argument('--'+name,type=Path,required=True)
a=parser.parse_args();checks=[]
def need(ok,label):
    if not ok:raise ValueError(label)
    checks.append(label)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def obj(raw):
    def pairs(rows):
        data={}
        for key,value in rows:
            if key in data:raise ValueError('duplicate JSON key: '+key)
            data[key]=value
        return data
    return json.loads(raw,object_pairs_hook=pairs)
def git(*args):return subprocess.check_output(['git','-C',str(a.repo),*args],stderr=subprocess.PIPE,timeout=60)
def doc(commit,name):return git('show',commit+':docs/nodes/n47l-evidence/'+name)
def blocks(text):
    rows=text.splitlines();out=[]
    for i,row in enumerate(rows):
        if row=='        run: |':
            body=[]
            for following in rows[i+1:]:
                if following and not following.startswith('          '):break
                body.append(following[10:] if following else '')
            out.append('\n'.join(body)+'\n')
    return out
source='17e9a435f94e45b3ca22d3da062ba4683c135c4b';source_tree='f9d42819772df53dd8c6337c3cb19c8940d7023a'
pins=obj(a.pins.read_bytes());facts=obj(a.github_facts.read_bytes())
keys={'REVIEW_SHA','REVIEW_TREE','MERGE_SHA','METADATA_SHA256','SUMMARY_SHA256','VERIFIER_SHA256','READBACK_CHECKS','PACKAGE_BYTES','PACKAGE_SHA256','EXE_BYTES','EXE_SHA256'}
need(set(pins)==keys and all(isinstance(v,str) for v in pins.values()),'exactly eleven string-valued final pin substitutions')
review=pins['REVIEW_SHA'];merge=pins['MERGE_SHA'];review_tree=pins['REVIEW_TREE']
original=a.template.read_bytes();final=a.workflow.read_bytes()
need(sha(original)=='aad1e079a252ce58dff3decebf95f040c46979530da75af3c9236d73cd7e651a','corrected independently reviewed template bytes')
need(sha(final)=='389b6f38cf695e2f1ebfe149761e45ccd5b8dac35142f97e8ff1650991fe7a3a','exact final workflow bytes')
expected=original.decode()
for key,value in pins.items():
    expected,n=re.subn(r"(?m)^      "+key+r": 'REPLACE_[^']+'$",'      '+key+": '"+value+"'",expected)
    need(n==1,'one permitted env substitution: '+key)
def no_header(text):
    rows=text.splitlines(keepends=True)
    while rows and (rows[0].startswith('#') or not rows[0].strip()):rows.pop(0)
    return ''.join(rows)
need(no_header(expected)==no_header(final.decode()),'all remaining workflow bytes equal; only eleven env values and initial comments changed')
before_blocks=blocks(original.decode());after_blocks=blocks(final.decode())
need(len(before_blocks)==len(after_blocks)==2 and before_blocks==after_blocks,'both executable Python blocks are byte-identical to the reviewed template')
for block in after_blocks:ast.parse(block)
env=dict(re.findall(r"(?m)^      ([A-Z_0-9]+): '([^'\r\n]*)'$",final.decode()))
need(all(env.get(k)==v for k,v in pins.items()) and not any('REPLACE' in v for v in env.values()),'all concrete env pins match manifest; no unresolved env value')
need(env['SOURCE_SHA']==source and env['SOURCE_TREE']==source_tree and env['N44_RUN']=='35228307025' and env['N42_RUN']=='35228306922','source tree and workflow run pins stay fixed')
prelude='''import os,sys\ndef deny(event,args):\n    if event.startswith("socket.") or event in ("subprocess.Popen","os.system","os.posix_spawn","os.rename","os.mkdir","os.remove","os.rmdir","os.symlink","os.link","os.chmod","os.chown","os.truncate"):\n        raise AssertionError("Forbidden side effect: "+event)\n    if event=="open" and ((isinstance(args[1],str) and any(c in args[1] for c in "awx+")) or (isinstance(args[2],int) and args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))):\n        raise AssertionError("Forbidden file mutation")\nsys.addaudithook(deny)\n'''
first=subprocess.run([sys.executable,'-I','-S','-B','-c',prelude+after_blocks[0]],env={**env,'PATH':os.environ['PATH']},capture_output=True,text=True,timeout=20)
need(first.returncode==0,'filled-pin first guard executed successfully with external and file mutations denied')
pr=facts['pr28']
need(pr['number']==28 and pr['merged'] is True and pr['state']=='closed' and pr['merge_commit_sha']==merge and pr['head_sha']==review and pr['head_repository']==pr['base_repository']=='youq616/qbrain' and pr['base_ref']=='main','actual GitHub PR 28 merged status/head/merge/repositories/main binding')
need(facts['source']['commit']==source and facts['source']['tree']==source_tree,'actual GitHub source commit/tree binding')
need(facts['review']['commit']==review and facts['review']['tree']==review_tree and facts['review']['parents']==[source],'actual GitHub review commit/tree and direct source parent')
need(facts['merge']['commit']==merge and facts['merge']['tree']==review_tree and review in facts['merge']['parents'],'actual GitHub merged commit has the exact reviewed tree')
need(git('rev-parse',source+'^{tree}').decode().strip()==source_tree and git('rev-parse',review+'^{tree}').decode().strip()==review_tree,'local Git object trees equal independently queried GitHub trees')
subprocess.run(['git','-C',str(a.repo),'merge-base','--is-ancestor',source,review],check=True,capture_output=True,timeout=60)
changed=[x.decode() for x in git('diff','--name-only','--no-renames','-z',source,review,'--').split(b'\0') if x]
need(len(changed)==49 and all(name.startswith('docs/') for name in changed),'source-to-review diff is exactly 49 docs-only paths')
committed_template=doc(review,'n47l-publish-template.yml')
need(committed_template==original,'review commit contains the exact independently reviewed publication template')
file_keys={'CI-METADATA.json':'METADATA_SHA256','SUMMARY.json':'SUMMARY_SHA256','verify_candidate.py':'VERIFIER_SHA256'}
file_hashes={}
for name,key in file_keys.items():
    raw=doc(review,name);file_hashes[name]={'sha256':sha(raw),'bytes':len(raw)}
    need(file_hashes[name]['sha256']==pins[key],'committed document bytes bind final pin: '+name)
summary=obj(doc(review,'SUMMARY.json'));metadata=obj(doc(review,'CI-METADATA.json'));readback_bytes=doc(review,'READBACK.json');readback=obj(readback_bytes)
need(summary['source_commit']==metadata['source_commit']==readback['source_commit']==source and summary['source_tree']==metadata['source_tree']==readback['source_tree']==source_tree,'summary metadata and readback all name the exact tested source/tree')
need(summary['scoped_result']=='PASS_SCOPED' and summary['independent_subagent_reviewed'] is True and type(summary['unresolved_scoped_p0_p1_p2']) is int and summary['unresolved_scoped_p0_p1_p2']==0 and all(summary['reviews'][scope]=='PASS_SCOPED' for scope in ('storage','interface','ci_artifact_readback','publication_control')),'committed outcome closes all scoped reviews without unresolved findings')
need(summary['publication_control']['template_sha256']==sha(original) and summary['publication_control']['actual_publication_at_outcome_review'] is False,'outcome binds approved template without claiming prior publication')
need(sha(readback_bytes)==summary['readback']['report_sha256'] and readback['result']=='PASS','committed successful readback bytes match summary report hash')
need(type(readback['check_count']) is int and readback['check_count']==summary['readback']['check_count']==int(pins['READBACK_CHECKS'])==1094,'final readback count equals committed actual 1094 checks')
need(readback['metadata_sha256']==summary['readback']['metadata_sha256']==pins['METADATA_SHA256'] and summary['readback']['verifier_sha256']==pins['VERIFIER_SHA256'],'readback metadata/verifier provenance equals final document pins')
runs={'n44':35228307025,'n42':35228306922}
need(readback['workflow_runs']==summary['workflow_runs']==runs and {k:metadata['runs'][k]['id'] for k in runs}==runs,'all evidence refers to the two fixed workflow runs')
need(len(metadata['artifacts'])==7 and readback['artifact_ids']==summary['readback']['artifact_ids']=={k:v['id'] for k,v in metadata['artifacts'].items()},'all seven artifact IDs agree across committed evidence')
need(readback['package']==summary['readback']['package'] and readback['package']['bytes']==int(pins['PACKAGE_BYTES']) and readback['package']['sha256']==pins['PACKAGE_SHA256'],'original inner package size/hash equals final pins and committed readback')
need(readback['exe']==summary['readback']['exe'] and readback['exe']['bytes']==int(pins['EXE_BYTES']) and readback['exe']['sha256']==pins['EXE_SHA256'],'packaged EXE size/hash equals final pins and committed readback')
need(readback['report_summaries']['windows']['multiterm-process']=={'checks':112,'commands':126} and readback['report_summaries']['windows']['multiterm-unit']=={'scenarios':16,'assertions':258},'fixed native N47L report counts match workflow gates')
raw=a.package_artifact.read_bytes();package_pin=metadata['artifacts']['package']
need(len(raw)==package_pin['size_in_bytes'] and sha(raw)==package_pin['sha256'],'locally retained original CI package artifact bytes match pinned artifact digest/size')
with zipfile.ZipFile(io.BytesIO(raw)) as wrapper:
    need(wrapper.getinfo('qbrain-windows-x64-development.zip').file_size<128*1024*1024,'inner package stays bounded before read')
    package=wrapper.read('qbrain-windows-x64-development.zip')
need(len(package)==int(pins['PACKAGE_BYTES']) and sha(package)==pins['PACKAGE_SHA256'],'direct original inner ZIP rehash independently confirms final package pins')
with zipfile.ZipFile(io.BytesIO(package)) as archive:
    need(archive.getinfo('qbrain.exe').file_size<128*1024*1024,'packaged EXE stays bounded before read')
    exe=archive.read('qbrain.exe')
need(len(exe)==int(pins['EXE_BYTES']) and sha(exe)==pins['EXE_SHA256'],'direct packaged EXE rehash independently confirms final executable pins')
report={'result':'PASS_FINAL_PINS_SCOPED','reviewer':'/root/recall_storage_review','scope':'Final factual bindings and byte identity to the independently reviewed publication template; not actual publication','check_count':len(checks),'checks':checks,'workflow_sha256':sha(final),'reviewed_template_sha256':sha(original),'pins_manifest_sha256':sha(a.pins.read_bytes()),'pins':pins,'fixed_source':{'commit':source,'tree':source_tree},'fixed_runs':runs,'github_observation':facts,'source_to_review_changed_paths':changed,'committed_evidence':file_hashes,'readback':{'sha256':sha(readback_bytes),'check_count':readback['check_count'],'package':readback['package'],'exe':readback['exe']},'controls_unchanged':True,'python_blocks_byte_identical':True,'filled_guard_execution_exit':first.returncode,'original_ci_artifact_rehashed':True,'inner_zip_and_exe_rehashed':True,'product_executed':False,'live_ci_runs_requeried_in_this_pin_check':False,'network_operations':'GitHub plugin read-only GET for PR and source/review/merge Git commits only','publication_performed':False,'unresolved_scoped_p0_p1_p2':0}
with a.report.open('x') as stream:stream.write(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'result':report['result'],'checks':report['check_count'],'workflow_sha256':report['workflow_sha256'],'changed_docs':len(changed)}))
