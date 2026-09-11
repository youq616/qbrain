"""Real native Qbrain processes with documented host event fixtures (no live model)."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile


def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True)
    binary=p.parse_args().binary.resolve(strict=True)
    checks=0
    def check(ok,label):
        nonlocal checks
        if not ok: raise AssertionError(label)
        checks+=1;print(f'PASS {checks}: {label}',flush=True)
    with tempfile.TemporaryDirectory(prefix='qbrain-hooks-') as t:
        root=Path(t)/'中文 project 😀';root.mkdir()
        project=root/'project';project.mkdir()
        outside=root/'not-project';outside.mkdir()
        settings=root/'trusted';settings.mkdir()
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
        env.update(HOME=str(root),LOCALAPPDATA=str(root),USERPROFILE=str(root))
        def cli(*args,data=None):
            x=subprocess.run([str(binary),*args,'--brain','hooks-ci'],cwd=project,env=env,input=None if data is None else json.dumps(data,ensure_ascii=False).encode(),capture_output=True,timeout=15)
            if x.returncode: raise AssertionError(x.stderr.decode(errors='replace')+x.stdout.decode(errors='replace'))
            return x.stdout.decode('utf-8')
        cli('init')
        data_root=root if os.name=='nt' else root/'.local'/'share'
        dbpath=data_root/'Qbrain'/'brains'/'hooks-ci'/'brain.db'
        def snapshot():
            with closing(sqlite3.connect(dbpath)) as db:
                names=[r[0] for r in db.execute("select name from sqlite_master where type='table' order by name")]
                return {n:db.execute('select * from "'+n+'"').fetchall() for n in names}
        quote='我偏好 PostgreSQL，不使用 Docker Hub。'
        for host in ('claude','codex'):
            config=settings/(host+'.json')
            cfg=dict(version=1,host=host,project_root=str(project),brain_id='hooks-ci',source_id='default',enabled=True,capture=True,extraction='local',recall_bytes=2048,max_items=8)
            config.write_text(json.dumps(cfg,ensure_ascii=False),encoding='utf-8')
            def event(kind,session='session-1',cwd=project,**extra):
                data=dict(hook_event_name=kind,session_id=session,cwd=str(cwd),**extra)
                x=subprocess.run([str(binary),'hook','--config',str(config)],env=env,cwd=cwd,input=json.dumps(data,ensure_ascii=False).encode(),capture_output=True,timeout=15)
                check(x.returncode==0,host+' hook returns non-blocking status')
                check(len(x.stdout)<=2049 and len(x.stdout.splitlines())==1,host+' emits one bounded JSON object')
                return json.loads(x.stdout)
            cli('config','set','memory.writeback','off')
            before=snapshot()
            event('UserPromptSubmit',session='off',prompt='I prefer paused capture')
            check(snapshot()==before,host+' automatic off cannot mutate application tables')
            cli('config','set','memory.writeback','salient')
            event('UserPromptSubmit',prompt=quote,turn_id='one',transcript_path=str(outside/'never-read-secret'))
            r=json.loads(cli('memory','read','--query','PostgreSQL'))
            check(any(x['quote']==quote for x in r['items']),host+' user event automatically captured and extracted')
            before=snapshot()
            event('UserPromptSubmit',prompt=quote,turn_id='one')
            check(snapshot()==before,host+' retry is idempotent even across native process exits')
            out=event('SessionStart',session='restart')
            check(quote in out.get('hookSpecificOutput',{}).get('additionalContext',''),host+' new session recovers exact memory')
            check('decision' not in out and 'continue' not in out,host+' does not control user workflow')
            out=event('UserPromptSubmit',session='restart',prompt='Please check PostgreSQL deployment')
            check(out=={},host+' recent output is deduplicated within a session')
            event('PreCompact',session='restart')
            out=event('UserPromptSubmit',session='restart',prompt='Please check PostgreSQL deployment')
            check(quote in out.get('hookSpecificOutput',{}).get('additionalContext',''),host+' compaction permits refreshed lexical recall')
            event('Stop',session='restart',last_assistant_message='I prefer to invent another user preference.')
            r=json.loads(cli('memory','read'))
            check(all('invent' not in i['quote'] for i in r['items']),host+' assistant message is never promoted to user memory')
            before=snapshot()
            event('UserPromptSubmit',session='secret',prompt='password=synthetic-do-not-store')
            check(snapshot()==before,host+' credential material is refused before archive')
            trace=json.loads((settings/'last-trace.json').read_text())
            check(trace['host_consumption_confirmed'] is False and quote not in json.dumps(trace),host+' trace never claims consumption or logs prompts')
            before=snapshot()
            event('UserPromptSubmit',cwd=outside,prompt='I prefer the wrong project')
            check(snapshot()==before,host+' fixed config rejects an unrelated working directory')
            cfg['enabled']=False;config.write_text(json.dumps(cfg),encoding='utf-8')
            event('UserPromptSubmit',prompt='I prefer disabled integration')
            check(snapshot()==before,host+' disabled configuration is inert')
        check(json.loads(cli('memory','read','--query','wrong project'))['items']==[], 'no cross-project capture persisted')
        print(f'N44B documented-host fixture checks: {checks} passed; actual model/host consumption not emulated.')

if __name__=='__main__':main()
