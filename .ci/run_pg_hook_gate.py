"""N48R fixed-source native Hook + retained PostgreSQL/SQLite qualification.
Requires explicitly provisioned synthetic PG databases; no automatic account access.
"""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True)
    a=p.parse_args();root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);(out/'gate-logs').mkdir(exist_ok=False)
    suffix='.exe' if os.name=='nt' else '';bindir=a.build.resolve()/('Release' if os.name=='nt' else '')
    env=os.environ.copy();env['PYTHONIOENCODING']='utf-8';env['PYTHONDONTWRITEBYTECODE']='1';records=[]
    def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
    def run(name,args,extra=None,destination=None):
        target=out/(destination or ('gate-logs/'+name+'.log'));target.parent.mkdir(parents=True,exist_ok=True)
        row={'name':name,'args':list(map(str,args)),'status':'started'};records.append(row)
        (out/'hook-gate-driver.json').write_text(json.dumps(records,indent=2),encoding='utf8')
        with target.open('wb') as f: result=subprocess.run(row['args'],cwd=root,env={**env,**(extra or {})},stdout=f,stderr=subprocess.STDOUT,timeout=1800)
        row.update(status='completed',exit=result.returncode,log=str(target.relative_to(out)),sha256=digest(target))
        (out/'hook-gate-driver.json').write_text(json.dumps(records,indent=2),encoding='utf8')
        if result.returncode:raise RuntimeError('failed '+name)
    programs={'qbrain':'qbrain','pg-hook-tests':'qbrain_pg_hook_tests','pg-fact-tests':'qbrain_pg_fact_tests','pg-context-tests':'qbrain_pg_context_tests','pg-memory-tests':'qbrain_pg_memory_tests','pg-scope-tests':'qbrain_pg_memory_scope_tests'}
    for dest,source in programs.items():shutil.copy2(bindir/(source+suffix),out/(dest+suffix))
    binary=out/('qbrain'+suffix);initial=digest(binary)
    pin=subprocess.check_output([sys.executable,str(root/'.ci/run_pg_memory_gate.py'),'pin','--artifact',str(out),'--binary',str(bindir/('qbrain'+suffix)),'--commit',env['GITHUB_SHA'],'--tree',subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root,text=True).strip(),'--platform','windows' if os.name=='nt' else 'linux'],cwd=root,env=env,text=True).strip()
    if len(pin)!=64:raise RuntimeError('pin failed')
    (out/'review-pin.sha256').write_text(pin+'\n')
    # Explicit localhost test DSNs only; never discover or use a user's database.
    def dsn(db):return f"host=127.0.0.1 port={env['PGPORT']} dbname={db} user=qbrain_n48o password=n48o-synthetic-only connect_timeout=5"
    extra={
      'QBRAIN_PG_MEMORY_TEST_DISPOSABLE':'1','QBRAIN_PG_MEMORY_TEST_DSN':dsn('qbrain_n48o_native'),'QBRAIN_PG_PROCESS_TEST_DSN':dsn('qbrain_n48o_process'),
      'QBRAIN_PG_CONTEXT_TEST_DISPOSABLE':'1','QBRAIN_PG_CONTEXT_TEST_DSN':dsn('qbrain_n48p_native'),'QBRAIN_PG_CONTEXT_PROCESS_DSN':dsn('qbrain_n48p_process'),
      'QBRAIN_PG_FACT_TEST_DISPOSABLE':'1','QBRAIN_PG_FACT_TEST_DSN':dsn('qbrain_n48q_native'),'QBRAIN_PG_FACT_PROCESS_DSN':dsn('qbrain_n48q_process'),
      'QBRAIN_PG_HOOK_TEST_DISPOSABLE':'1','QBRAIN_PG_HOOK_DSN':dsn('qbrain_n48r_native'),'QBRAIN_PG_HOOK_PROCESS_DSN':dsn('qbrain_n48r_process'),'QBRAIN_PG_HOOK_EMPTY_DSN':dsn('qbrain_n48r_empty')}
    # Keep all earlier live PG modules: no mocks or skipped PG prerequisites.
    for name,dest in [('pg-memory-tests','native-result.json'),('pg-scope-tests','scope-result.json'),('pg-context-tests','context-native.json'),('pg-fact-tests','fact-native.json'),('pg-hook-tests','hook-native.json')]:
        run(name,[out/(name+suffix)],extra,dest)
    for mode in ('normal','optimized'):
        py=[sys.executable]+(['-O'] if mode=='optimized' else [])
        for label,script,db in [('process','test_pg_memory','qbrain_n48o_process'),('context','test_pg_context','qbrain_n48p_process'),('fact','test_pg_facts','qbrain_n48q_process'),('hook','test_pg_hooks','qbrain_n48r_process')]:
            run(label+'-'+mode,py+[root/'.ci'/(script+'.py'),'--binary',binary,'--output',out/(label+'-'+mode)],{**extra,'PGDATABASE':db})
            if label=='process':run('dump-memory-'+mode,['pg_dump','--no-owner','--no-privileges','--format=plain'],{**extra,'PGDATABASE':db},'synthetic-process.sql' if mode=='optimized' else 'synthetic-process-normal.sql')
        for name in ('test_hooks','test_memory_cycle'):
            run(name+'-'+mode,py+[root/'.ci'/(name+'.py'),'--binary',binary])
        run('session-review-'+mode,py+[root/'.ci/review_session_lifecycle.py','--binary',binary,'--output',out/'integrated'/('lifecycle-'+mode)])
    for mode in ('normal','optimized'):
        py=[sys.executable]+(['-O'] if mode=='optimized' else [])
        run('integrated-readback-'+mode,py+[root/'.ci/run_pg_memory_gate.py','verify','--artifact',out,'--pin-sha256',pin,'--output',out/'integrated'/('review-'+mode+'.json')])
    run('retained-55',[sys.executable,root/'.ci/run_n48i_checks.py','--binary',binary,'--baseline',a.baseline.resolve(),'--output',out/'retained'])
    if digest(binary)!=initial:raise RuntimeError('binary changed')
    run('source-unchanged',['git','diff','--exit-code'])
    print(json.dumps({'schema':'qbrain-n48r-gate-v1','passed':True,'steps':len(records),'binary_sha256':initial,'source_commit':env['GITHUB_SHA']}))
if __name__=='__main__':main()
