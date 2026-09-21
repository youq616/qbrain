"""Pinned official OpenCode V1 config loading; V2 is its compatibility reader.

Fetch only in the network-enabled step; execute only in an isolated Linux network
namespace. No user configuration, credentials, provider prompt or tools/call.
"""
from __future__ import annotations
import argparse, hashlib, io, json, os, re, signal, subprocess, tarfile, tempfile, zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler, urlopen

SOURCE='e419acf60375e1a7a0794375c713f759b776aa0b'
RUN=35612180651
UPSTREAM_RELEASE=388581987
UPSTREAM_TAG='v1.18.31'
UPSTREAM_COMMIT='a97622c801f4ca571530ddc51076af659a9c32cd'
UPSTREAM_ASSET=563876677
UPSTREAM_BYTES=60590585
UPSTREAM_SHA='b283e8dbe9e6fc224bb4b79992ce3bd2174b8b7b0c3e7d1b4e6024a1d11edc84'


def need(ok, why):
    if not ok:raise ValueError(why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def encoded(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
def get(url,limit=4*1024*1024,token=None):
    headers={'User-Agent':'qbrain-n48e-verification','Accept':'application/vnd.github+json'}
    if token:headers['Authorization']='Bearer '+token
    with urlopen(Request(url,headers=headers),timeout=90) as r:raw=r.read(limit+1)
    need(len(raw)<=limit,'download bound');return raw


def fetch(output):
    output.mkdir(parents=True,exist_ok=False)
    token=os.environ.get('GH_TOKEN')
    api='https://api.github.com/repos/youq616/qbrain'
    run=json.loads(get(f'{api}/actions/runs/{RUN}',token=token))
    need(run['head_sha']==SOURCE and run['event']=='push' and run['run_attempt']==1,'source run identity')
    listing=json.loads(get(f'{api}/actions/runs/{RUN}/jobs?per_page=100',token=token))
    job=next(j for j in listing['jobs'] if j['name']=='portable')
    need(job['status']=='completed' and job['conclusion']=='success','portable candidate not passed')
    listing=json.loads(get(f'{api}/actions/runs/{RUN}/artifacts',token=token))
    artifact=next(a for a in listing['artifacts'] if a['name']=='qbrain-n48e-portable')
    need(not artifact['expired'] and artifact['workflow_run']['head_sha']==SOURCE,'artifact identity')
    # Follow artifact redirect with a new UNAUTHENTICATED request; never send the
    # repository workflow token to the signed storage host.
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    headers={'User-Agent':'qbrain-n48e-verification'}
    if token:headers['Authorization']='Bearer '+token
    try:
        build_opener(NoRedirect).open(Request(artifact['archive_download_url'],headers=headers),timeout=60)
        raise ValueError('Expected artifact download redirect')
    except HTTPError as e:
        need(e.code in (301,302,303,307,308),'artifact API error');url=e.headers['Location']
    need(urlparse(url).scheme=='https','non-HTTPS artifact destination')
    raw=get(url,128*1024*1024)
    need(len(raw)==artifact['size_in_bytes'] and 'sha256:'+sha(raw)==artifact['digest'],'artifact bytes')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        need(z.testzip() is None,'artifact CRC')
        need(z.read('source.txt').decode('utf-8-sig').strip()==SOURCE,'artifact source marker')
        binary=z.read('qbrain');need(len(binary)<32*1024*1024,'binary bound')
    (output/'qbrain').write_bytes(binary);(output/'qbrain').chmod(0o755)
    release=json.loads(get(f'https://api.github.com/repos/anomalyco/opencode/releases/{UPSTREAM_RELEASE}'))
    need(release['tag_name']==UPSTREAM_TAG and release['target_commitish']==UPSTREAM_COMMIT and release['immutable'] is True,'upstream release identity')
    asset=next(a for a in release['assets'] if a['name']=='opencode-linux-x64-baseline.tar.gz')
    need(asset['id']==UPSTREAM_ASSET and asset['size']==UPSTREAM_BYTES and asset['digest']=='sha256:'+UPSTREAM_SHA and asset['state']=='uploaded' and asset['browser_download_url'].startswith(f'https://github.com/anomalyco/opencode/releases/download/{UPSTREAM_TAG}/'),'upstream asset source')
    package=get(asset['browser_download_url'],256*1024*1024)
    need(len(package)==asset['size'] and 'sha256:'+sha(package)==asset['digest'],'upstream asset bytes')
    with tarfile.open(fileobj=io.BytesIO(package),mode='r:gz') as t:
        members=[m for m in t.getmembers() if Path(m.name).name=='opencode']
        need(len(members)==1 and members[0].isfile() and members[0].size<=256*1024*1024,'upstream executable member')
        executable=t.extractfile(members[0]).read()
    (output/'opencode').write_bytes(executable);(output/'opencode').chmod(0o755)
    (output/'PROVENANCE.json').write_bytes(encoded({'candidate_run':RUN,'candidate_source':SOURCE,'candidate_job':job['id'],
        'artifact':artifact,'qbrain_sha256':sha(binary),'opencode_asset':asset,'opencode_sha256':sha(executable),
        'opencode_tag':UPSTREAM_TAG,'opencode_source':UPSTREAM_COMMIT,'upstream_immutable':True}))


def run(inputs,output):
    output.mkdir(parents=True,exist_ok=False);records=[];checks=[];failure=None;scenarios=0
    def check(ok,name):
        checks.append({'name':name,'passed':bool(ok)})
        if not ok:raise ValueError(name)
    provenance=json.loads((inputs/'PROVENANCE.json').read_bytes())
    qb=(inputs/'qbrain').resolve(strict=True);host=(inputs/'opencode').resolve(strict=True)
    try:
        check({p.name for p in Path('/sys/class/net').iterdir()}=={'lo'},'execution has loopback-only network namespace')
        check(sha(qb.read_bytes())==provenance['qbrain_sha256'] and sha(host.read_bytes())==provenance['opencode_sha256'],'executed bytes match fetched provenance')
        with tempfile.TemporaryDirectory(prefix='n48e-actual-host-') as tmp:
            root=Path(tmp);home=root/'home';home.mkdir()
            env={'PATH':'/usr/local/bin:/usr/bin:/bin','LANG':'C.UTF-8','HOME':str(home),'USERPROFILE':str(home),
                 'LOCALAPPDATA':str(home),'APPDATA':str(home),'XDG_CONFIG_HOME':str(home/'config'),
                 'XDG_DATA_HOME':str(home/'data'),'XDG_CACHE_HOME':str(home/'cache'),'XDG_STATE_HOME':str(home/'state'),
                 'OPENCODE_DISABLE_AUTOUPDATE':'1','OPENCODE_DISABLE_MODELS_FETCH':'1','OPENCODE_PURE':'1',
                 'OPENCODE_EXPERIMENTAL_DISABLE_FILEWATCHER':'1','NO_COLOR':'1','CI':'true'}
            def call(exe,args,cwd,code=0):
                p=subprocess.Popen([str(exe),*args],cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
                try:stdout,stderr=p.communicate(timeout=45)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid,signal.SIGKILL);stdout,stderr=p.communicate()
                    records.append({'exe':'opencode' if exe==host else 'qbrain','args':args,'exit':p.returncode,
                                    'stdout':stdout.decode(errors='replace'),'stderr':stderr.decode(errors='replace'),'timed_out':True})
                    (output/'records.json').write_bytes(encoded(records));raise ValueError('host fixture timeout')
                records.append({'exe':'opencode' if exe==host else 'qbrain','args':args,'cwd':str(cwd),'exit':p.returncode,
                                'stdout':stdout.decode(),'stderr':stderr.decode()})
                (output/'records.json').write_bytes(encoded(records))
                need(p.returncode==code,'actual command exit')
                return stdout.decode(),stderr.decode()
            version,_=call(host,['--version'],root)
            check(version.strip()==UPSTREAM_TAG[1:],'actual official executable version')
            for fmt in ('v1','v2'):
                for write in (False,True):
                    project=root/(fmt+('-write' if write else '-read'));project.mkdir()
                    options=['--project',str(project),'--binary',str(qb),'--brain','host-fixture','--format',fmt]
                    if write:options+=['--allow-write']
                    def q(args,code=0):return json.loads(call(qb,['opencode',*args],root,code)[0])
                    plan=q(['preview',*options]);q(['install',*options,'--approve-sha256',plan['plan_sha256']])
                    cfg=project/'opencode.jsonc';before=cfg.read_bytes();name=plan['server_name']
                    resolved=json.loads(call(host,['debug','config'],project)[0]);entry=resolved['mcp'][name]
                    expected=[str(qb),'serve','--brain','host-fixture','--tool-profile','memory']+(['--allow-write'] if write else [])
                    check(entry['command']==expected and entry.get('enabled') is True and entry['cwd']==str(project),fmt+' actual loader keeps target and enablement')
                    check(entry['environment']=={'QBRAIN_MCP_ALLOW_WRITE':'0'} and entry.get('timeout')==10000,fmt+' actual loader preserves explicit environment and timeout')
                    if cfg.read_bytes()!=before:
                        prior=json.loads(before);now=json.loads(cfg.read_bytes());now.pop('$schema',None)
                        check(now==prior,fmt+' host only adds schema to managed configuration')
                        check(q(['status','--project',str(project)])['configuration_matches'] is False,fmt+' host rewrite is visible as drift')
                        approval=q(['reconcile-preview','--project',str(project)])
                        q(['reconcile','--project',str(project),'--approve-sha256',approval['plan_sha256']])
                    text,err=call(host,['mcp','list'],project)
                    text=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text+'\n'+err)
                    check(re.search(re.escape(name)+r'\s+connected\b',text) is not None,fmt+' actual host reports this generated MCP server connected')
                    check(q(['status','--project',str(project)])['configuration_matches'] is True,fmt+' connection leaves reconciled configuration coherent')
                    un=q(['uninstall-preview','--project',str(project)])
                    q(['uninstall','--project',str(project),'--approve-sha256',un['plan_sha256']])
                    check(not cfg.exists() or name not in cfg.read_text(),fmt+' explicit uninstall removes only managed registration')
                    scenarios+=1
            check(scenarios==4,'four actual host loading and connection scenarios completed')
    except Exception as e:failure=type(e).__name__+': '+str(e)
    report={'schema':'qbrain-n48e-real-host-v1','result':'PASS' if failure is None else 'FAIL','failure':failure,'checks':checks,
        'scenarios_completed':scenarios,'records':records,'provenance':provenance,'host_engine':'OpenCode V1 '+UPSTREAM_TAG,
        'v2_engine_tested':False,'v2_scope':'V1 compatibility loader for V2 configuration',
        'model_prompts_sent':0,'tools_call_requested':0,'network_namespace':'loopback-only','real_user_brain_supplied':False,
        'host_consumption_verified':False}
    (output/'report.json').write_bytes(encoded(report))
    print(json.dumps({k:v for k,v in report.items() if k not in ('records','checks','provenance')}))
    if failure:raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['fetch','run'])
    p.add_argument('--inputs',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.action=='fetch':fetch(a.output)
    else:run(a.inputs,a.output)
