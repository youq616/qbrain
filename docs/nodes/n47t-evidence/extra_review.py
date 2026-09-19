"""Separately authored N47T self-review; disposable public-CLI facts, SQL readback only."""
from pathlib import Path
import argparse, hashlib, json, os, sqlite3, subprocess, tempfile, time
from contextlib import closing
p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
exe=a.binary.resolve();checks=[];commands=[]
def sha(b):return hashlib.sha256(b).hexdigest()
def need(ok,name):
 checks.append({'name':name,'passed':bool(ok)})
 if not ok:raise AssertionError(name)
try:
 with tempfile.TemporaryDirectory(prefix='n47t-extra-') as tmp:
  root=Path(tmp);env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))};env.update(HOME=tmp,USERPROFILE=tmp,LOCALAPPDATA=tmp,APPDATA=tmp)
  dbpath=(root if os.name=='nt' else root/'.local/share')/'Qbrain/brains/review/brain.db'
  def call(args,payload=None,code=0,raw=False):
   data=b'' if payload is None else json.dumps(payload,ensure_ascii=False).encode()
   q=subprocess.run([str(exe),*args,'--brain','review'],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,cwd=root,timeout=30)
   commands.append({'argv':args,'exit':q.returncode,'expected_exit':code,'stdout_sha256':sha(q.stdout),'stderr_sha256':sha(q.stderr)})
   if q.returncode!=code:raise AssertionError(str((args,q.returncode,q.stdout)))
   commands[-1]['stdout']=q.stdout.decode(errors='replace')
   return q.stdout if raw else json.loads(q.stdout)
  def sql(s,vals=()):
   with closing(sqlite3.connect(dbpath)) as db:return db.execute(s,vals).fetchall()
  def seed(name,expires=0):
   ev=call(['memory','capture','--manual'],{'session_id':'review','fragment_id':name,'expires_at':expires,'messages':[{'role':'user','content':'I prefer supplemental review evidence.'}]})['event_id']
   call(['memory','extract','--event',ev]);rows=call(['memory','read'])['items'];item=next(x for x in rows if x['event_id']==ev)
   f=call(['fact','create'],{'item_id':item['item_id'],'predicate':'review.preference'})
   return f,ev,item
  def report(f,label,code=0):return call(['fact','report-use'],{'fact_id':f['fact_id'],'usage_id':sha(label.encode()),'expected_revision':f['revision']},code)
  call(['init','--no-default'],raw=True);call(['config','set','memory.writeback','salient','--local'],raw=True)
  f,event,item=seed('stable')
  need(call(['fact','revoke-use'],{'fact_id':f['fact_id'],'usage_id':'a'*64},1)['error']['code']=='fact_usage_not_found','revoking missing receipt does not create one')
  need(sql("SELECT count(*) FROM sqlite_master WHERE name='memory_fact_usage_module'")[0][0]==0,'missing revoke leaves schema absent')
  prior=sql('SELECT * FROM memory_facts ORDER BY fact_id');report(f,'same-id')
  backups=list(dbpath.parent.glob('brain.db.pre-usage-v1-*.bak'));need(len(backups)==1,'single-process first report produces one premodule backup')
  with closing(sqlite3.connect(backups[0])) as db:
   need(db.execute('SELECT * FROM memory_facts ORDER BY fact_id').fetchall()==prior,'backup retains exact prior fact rows')
   need(db.execute("SELECT count(*) FROM sqlite_master WHERE name='memory_fact_usage_module'").fetchone()[0]==0,'backup predates optional schema')
  other,_,item2=seed('new-support');f2=call(['fact','attach'],{'fact_id':f['fact_id'],'item_id':item2['item_id']})
  need(report(f2,'same-id',1)['error']['code']=='fact_usage_id_conflict','same receipt ID cannot claim a new revision')
  u=call(['fact','usage','--id',f['fact_id']]);need(u['current_revision_use_count']==0 and u['other_revision_use_count']==1,'rejected revision retarget leaves historical-only count')
  exp=int(time.time())+10;f3,evt3,item3=seed('expiring',exp);report(f3,'expires')
  while time.time()<=exp:time.sleep(.05)
  need(call(['fact','usage','--id',f3['fact_id']],code=1)['error']['code']=='fact_not_found','expired support is not exposed through usage view')
  need(report(f3,'expires-new',1)['error']['code']=='fact_not_found','expired fact cannot gain a new receipt')
  need(sql('SELECT count(*) FROM memory_fact_usage WHERE fact_id=?',(f3['fact_id'],))[0][0]==1,'expired failed request creates no extra row')
  withdrawn=call(['fact','revoke-use'],{'fact_id':f3['fact_id'],'usage_id':sha(b'expires')})
  need(withdrawn['status']=='withdrawn','expired claim receipt can still be withdrawn')
  call(['memory','forget','--event',evt3]);need(sql('SELECT count(*) FROM memory_fact_usage WHERE fact_id=?',(f3['fact_id'],))[0][0]==0,'explicit forgetting cleans expired receipt too')
except Exception as e:checks.append({'name':'unexpected_exception','passed':False,'error':type(e).__name__+': '+str(e)})
r={'schema':'qbrain-n47t-separate-review-v1','binary_sha256':sha(exe.read_bytes()),'script_sha256':sha(Path(__file__).read_bytes()),'checks':checks,'commands':commands,'passed':sum(x['passed'] for x in checks),'failed':sum(not x['passed'] for x in checks),'platform':os.name,'real_client_tested':False}
a.report.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k not in ('checks','commands')}));raise SystemExit(bool(r['failed']))
