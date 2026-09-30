"""Native Cursor adapter exercise, synthetic events only, no Cursor login.
Complete raw CLI results and new trace artifacts are retained; no producer imports.
"""
from pathlib import Path
from contextlib import closing
import argparse, hashlib, json, os, sqlite3, subprocess, tempfile

def encode(o):return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf8')
def sha(b):return hashlib.sha256(b).hexdigest()
def main(binary,output):
    binary=binary.resolve(strict=True);output.mkdir(parents=True,exist_ok=False);(output/'raw').mkdir()
    calls=[];checks=[]
    def need(ok,name):
        checks.append(dict(name=name,passed=bool(ok)))
        if not ok:raise ValueError(name)
    try:
        with tempfile.TemporaryDirectory(prefix='n48y-native-') as tmp:
            home=Path(tmp);project=home/'project space 中文😀';project.mkdir();other=home/'other';other.mkdir()
            env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','PG','CURSOR','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
            env.update(HOME=tmp,USERPROFILE=tmp,LOCALAPPDATA=tmp,APPDATA=tmp)
            env['CURSOR_TRANSCRIPT_PATH']=str(home/'not-readable');env['CURSOR_USER_EMAIL']='SECRET_EMAIL'
            config=home/'config.json';cfg=dict(version=1,enabled=True,host='cursor',project_root=str(project),brain_id='cursor-test',source_id='alpha',capture=False,extraction='local',recall_bytes=8192,max_items=8,fact_recall=False,fact_promotion=False)
            db=(home if os.name=='nt' else home/'.local/share')/'Qbrain/brains/cursor-test/brain.db'
            def call(args,data=b'',where=project):
                p=subprocess.run([str(binary),*args],input=data,env=env,cwd=where,capture_output=True,timeout=25)
                i=len(calls);hs={}
                for key,raw in [('stdin',data),('stdout',p.stdout),('stderr',p.stderr)]:
                    (output/'raw'/f'{i:03}.{key}').write_bytes(raw);hs[key]=sha(raw)
                calls.append(dict(args=args,exit=p.returncode,hashes=hs));need(p.returncode==0 and p.stderr==b'','actual native successful exit')
                return p.stdout
            def q(args,data=None):return call([*args,'--brain','cursor-test'],b'' if data is None else encode(data))
            def sql(statement,params=(),read=False):
                with closing(sqlite3.connect(db)) as conn,conn:
                    cur=conn.execute(statement,params);return cur.fetchall() if read else None
            def hook(kind,session='session-A',generation='generation-A',**override):
                config.write_bytes(encode(cfg))
                raw=dict(hook_event_name=kind,conversation_id=session,generation_id=generation,workspace_roots=[str(project)],is_background_agent=False,
                    model='SECRET_MODEL',user_email='SECRET_EMAIL',transcript_path=str(home/'not-readable'),attachments=[dict(file_path=str(home/'not-readable'))])
                raw.update(override)
                return json.loads(call(['hook','--config',str(config)],encode(raw)))
            def counts():return sql('SELECT (SELECT count(*) FROM memory_events),(SELECT count(*) FROM memory_items),(SELECT count(*) FROM pages)',read=True)
            q(['init','--no-default']);q(['config','set','embed.auto','false','--local'])
            for src in ('alpha','beta'):sql('INSERT INTO sources(id,name) VALUES(?,?)',(src,src))
            q(['config','set','memory.writeback','salient','--local'])
            # Force normal native memory schema initialization, not synthetic DDL.
            payload=dict(session_id='foreign-seed',fragment_id='x',messages=[dict(role='user',content='I prefer FOREIGN_ONLY_SENTINEL.')])
            event=json.loads(q(['memory','capture','--source','beta','--manual'],payload))
            q(['memory','extract','--source','beta','--event',event['event_id']])
            before=counts();need(hook('beforeSubmitPrompt',prompt='I prefer NOT_AUTHORIZED.')=={'continue':True},'capture default off does not block')
            need(counts()==before,'default off prevents writes despite shared policy')
            need(hook('sessionStart')=={},'other source never injected')
            cfg['capture']=True
            quote='I prefer Windows C++ 中文😀 exactly.\r\n'
            need(hook('beforeSubmitPrompt',prompt=quote)=={'continue':True},'prompt capture no unsupported context injection')
            after=counts();need(after[0][0]==before[0][0]+1 and after[0][1]==before[0][1]+1,'real capture and local extraction')
            saved=sql("SELECT e.event_id,m.quote,m.category FROM memory_events e JOIN memory_items m ON e.event_id=m.event_id WHERE e.source_id='alpha'",read=True)
            need(saved[0][1]==quote and saved[0][2]=='preference','exact user evidence kept')
            need(hook('beforeSubmitPrompt',prompt=quote)=={'continue':True} and counts()==after,'same generation replay idempotent')
            need(hook('beforeSubmitPrompt',prompt='I prefer conflicting changed prompt.')=={'continue':True} and counts()==after,'conflicting generation cannot overwrite evidence')
            need(hook('afterAgentResponse',text='I prefer ASSISTANT_ONLY_SENTINEL.')=={},'assistant event is no-output')
            need(sql("SELECT count(*) FROM memory_items WHERE quote LIKE '%ASSISTANT_ONLY%'",read=True)==[(0,)],'assistant does not become user memory')
            recalled=hook('sessionStart',session='session-B',session_id='session-B')
            need(set(recalled)=={'additional_context'} and isinstance(recalled['additional_context'],str),'Cursor session-start field and full recall')
            need('FOREIGN_ONLY' not in str(recalled) and 'ASSISTANT_ONLY' not in str(recalled),'source and role exclusion')
            body=json.loads(recalled['additional_context'].split('\n',1)[1]);need(body[0]['quote']==quote,'exact evidence decoded from wire')
            # beforeSubmitPrompt must not issue memory reads or mark memory as delivered.
            before_state=(home/'recall-state.json').read_bytes()
            cfg['capture']=False
            need(hook('beforeSubmitPrompt',session='session-B',generation='B',prompt='Windows C++')=={'continue':True},'query-time no fabricated injection')
            need((home/'recall-state.json').read_bytes()==before_state,'no query-time emission changes')
            # Explicit opt-in fact path uses original evidence implementation.
            item=json.loads(q(['memory','read','--source','alpha']))['items'][0]['item_id']
            fact=json.loads(q(['fact','create','--source','alpha'],dict(predicate='tool.preference',item_id=item)))
            cfg['fact_recall']=True
            fact_context=hook('sessionStart',session='facts')['additional_context']
            need(quote in [fact['object'] for group in json.loads(fact_context.split('\n',1)[1])['fact_groups'] for fact in group['facts']], 'existing fact composer reaches Cursor wire')
            q(['fact','retract','--source','alpha'],dict(fact_id=fact['fact_id'],expected_revision=1))
            need(hook('sessionStart',session='retired')=={},'retired fact not revived by legacy lane')
            cfg['fact_recall']=False
            q(['memory','forget','--source','alpha','--event',saved[0][0]])
            need(hook('sessionStart',session='forgotten')=={},'forgotten evidence not recalled')
            cfg['capture']=True
            hook('beforeSubmitPrompt',prompt=quote)
            need(sql("SELECT count(*) FROM memory_items m JOIN memory_events e ON e.event_id=m.event_id WHERE e.source_id='alpha'",read=True)==[(0,)],'replay of forgotten generation remains forgotten')
            # Invalid scope/identity never mutates state or the database.
            variants=[dict(workspace_roots=[str(other)]),dict(workspace_roots=[str(project),str(other)]),dict(workspace_roots=[]),dict(cwd=str(other)),dict(session_id='mismatch'),dict(generation_id=''),dict(generation_id=3),dict(is_background_agent=True),dict(is_background_agent=1),dict(prompt=3),dict(prompt='x\0y')]
            for i,change in enumerate(variants):
                before=counts();state=(home/'recall-state.json').read_bytes();v=dict(prompt='I prefer INVALID_CAPTURE.',**{})
                v.update(change);need(hook('beforeSubmitPrompt',session='invalid'+str(i),**v)=={'continue':True},'malformed or foreign Cursor event fails open')
                need(counts()==before and (home/'recall-state.json').read_bytes()==state,'invalid event no persistence')
            for kind in ('stop','afterAgentThought','beforeReadFile','postToolUse','SessionStart'):
                before=counts();state=(home/'recall-state.json').read_bytes();need(hook(kind,prompt='I prefer UNSUPPORTED.')=={},'unsupported event has no action')
                need(counts()==before and state==(home/'recall-state.json').read_bytes(),'unsupported event no database/state write')
            before=counts();hook('beforeSubmitPrompt',session='secret',prompt='I prefer api_key=SECRET_CREDENTIAL')
            need(counts()==before,'sensitive user material never captured')
            q(['config','set','memory.writeback','off','--local']);before=counts()
            hook('beforeSubmitPrompt',session='off',prompt='I prefer BLOCKED_POLICY.')
            need(counts()==before,'shared policy remains independent consent')
            # Lifecycle cleanup, bounded native payload, and private metadata.
            hook('sessionStart',session='cleanup')
            key=sha(b'cursor\ncursor-test\nalpha\ncleanup')
            need(key in json.loads((home/'recall-state.json').read_bytes())['sessions'],'host-isolated session state')
            need(hook('preCompact',session='cleanup')=={},'precompact returns no invented context')
            need(key not in json.loads((home/'recall-state.json').read_bytes())['sessions'],'precompact removes state')
            hook('sessionStart',session='cleanup');hook('sessionEnd',session='cleanup')
            need(key not in json.loads((home/'recall-state.json').read_bytes())['sessions'],'session end removes state')
            traces=list(home.glob('trace-cursor-*.json'))
            need(len(traces)==5,'all five Cursor trace files actually produced')
            for path in traces:
                raw=path.read_bytes();trace=json.loads(raw)
                need(trace['host']=='cursor' and trace['host_consumption_confirmed'] is False and trace['provider_calls']==0,'metadata reports adapter not consumption')
                need(len(raw)<=4096 and b'SECRET_' not in raw and quote.encode() not in raw and str(project).encode() not in raw,'fixed metadata privacy')
                (output/path.name).write_bytes(raw)
            # Budget test with a fresh explicit full user statement.
            q(['config','set','memory.writeback','salient','--local']);cfg['capture']=True
            long_quote='I prefer '+('wide evidence 中文😀 '*75)
            hook('beforeSubmitPrompt',session='long',prompt=long_quote)
            need(sql("SELECT count(*) FROM memory_items WHERE quote=?",(long_quote,),read=True)==[(1,)],'long user statement actually extracted')
            for budget in (512,1024,8192):
                cfg['recall_bytes']=budget;out=hook('sessionStart',session='budget'+str(budget))
                need(len(encode(out))<=budget and ('hookSpecificOutput' not in out),'native Cursor response bounded without wrong envelope')
                if budget==8192:need(json.loads(out['additional_context'].split('\n',1)[1])[0]['quote']==long_quote,'large budget preserves complete long statement')
            # Unsupported config/envelope leaves default workflow nonblocking.
            cfg['enabled']=False;before=counts();need(hook('beforeSubmitPrompt',prompt='I prefer disabled.')=={} and counts()==before,'disabled installation inert')
    except Exception as e:
        (output/'PARTIAL.json').write_bytes(encode(dict(passed=False,error=str(e),commands=calls,checks=checks))+b'\n');raise
    report=dict(schema='qbrain-n48y-process-v1',passed=True,optimized=not __debug__,command_count=len(calls),check_count=len(checks),commands=calls,checks=checks,binary_sha256=sha(binary.read_bytes()),script_sha256=sha(Path(__file__).read_bytes()),real_cursor_session=False,paid_model_calls=0,postgres_executed=False)
    (output/'RESULT.json').write_bytes(encode(report)+b'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('commands','checks')}))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();main(a.binary,a.output)
