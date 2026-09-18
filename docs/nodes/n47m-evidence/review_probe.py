"""Separately authored N47M black-box review. Synthetic data, no model credentials.

This is a coordinator's additional engineering probe, not a separate reviewer.
Run against candidate and baseline separately; a failing baseline is expected.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import tempfile


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    exe = a.binary.resolve(strict=True)
    results, commands = [], []
    digest = lambda b: hashlib.sha256(b).hexdigest()
    def need(ok, why):
        if not ok:
            raise AssertionError(why)
    def check(name, f):
        start = len(commands)
        try:
            f()
            results.append({'name': name, 'passed': True, 'commands': [start, len(commands)]})
        except Exception as e:
            results.append({'name': name, 'passed': False, 'error': str(e), 'commands': [start, len(commands)]})
    with tempfile.TemporaryDirectory(prefix='n47m-review-') as td:
        root = Path(td) / '中文 😀'; root.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC'))}
        env.update(HOME=str(root), USERPROFILE=str(root), LOCALAPPDATA=str(root))
        data = (root if os.name == 'nt' else root / '.local/share') / 'Qbrain'
        def run(argv, payload=None, expected=0, extra=None):
            raw = b'' if payload is None else json.dumps(payload, ensure_ascii=False).encode()
            r = subprocess.run([str(exe), *argv], input=raw, cwd=root, env={**env, **(extra or {})},
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            commands.append({'argv': argv, 'stdin': raw.decode(), 'expected_exit': expected, 'exit': r.returncode,
                             'stdout_sha256': digest(r.stdout), 'stderr_sha256': digest(r.stderr)})
            need(r.returncode == expected, f'exit {r.returncode} != {expected}: {(r.stdout+r.stderr).decode(errors="replace")[:200]}')
            return r
        def obj(*args, **kwargs):
            return json.loads(run(*args, **kwargs).stdout)
        def sql(brain, text, values=()):
            with closing(sqlite3.connect(data/'brains'/brain/'brain.db')) as db:
                out = db.execute(text, values).fetchall(); db.commit(); return out
        def snapshot(brain):
            with closing(sqlite3.connect(data/'brains'/brain/'brain.db')) as db:
                tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                return digest(repr({t: sorted(db.execute('SELECT * FROM "'+t+'"').fetchall(), key=repr) for t in tables}).encode())
        def cfg(brain, key, value):
            sql(brain, 'INSERT INTO config(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key,value))
        brains = ['intended','environment','configured','default','--manual']
        tokens = ['--brain','--source','--limit','--max-bytes','--manual','--query']
        sources = ['alpha','--brain','--source','--layer','--uri','--offset','--revision','--max-bytes','--manual']
        events, quotes, pages = {}, {}, {}
        def payload(fragment, text):
            return {'session_id':'review','fragment_id':fragment,'messages':[{'role':'user','content':text}]}
        for brain in brains:
            run(['init','--brain',brain,'--no-default'])
            cfg(brain,'memory.writeback','salient')
            for source in (sources if brain=='intended' else ['alpha']):
                sql(brain,'INSERT INTO sources(id,name) VALUES(?,?)',(source,source))
                quote = 'I prefer '+brain+'/'+source+' literal '+' '.join(tokens)+' 中文😀'
                body = 'RAW '+brain+'/'+source+'\r\n中文😀 exact evidence.'
                cap = obj(['memory','capture','--brain',brain,'--source',source,'--manual'],payload(source,quote))
                obj(['memory','extract','--brain',brain,'--event',cap['event_id'],'--source',source])
                sql(brain,'INSERT INTO pages(source_id,slug,title,body) VALUES(?,?,?,?)',(source,'docs/a','Review',body))
                events[brain,source],quotes[brain,source],pages[brain,source]=cap['event_id'],quote,body
        def mem(argv, brain='intended', source='alpha', extra=None):
            r=obj(argv,extra=extra)
            need(r['source_id']==source,'wrong source')
            need(len(r['items'])==1,'missing or additional evidence')
            need(r['items'][0]['event_id']==events[brain,source],'wrong event')
            need(r['items'][0]['quote']==quotes[brain,source],'wrong brain/raw quotation')
        def ctx(argv, brain='intended', source='alpha', extra=None):
            r=obj(argv,extra=extra)
            need(r['source_id']==source,'wrong source')
            need(r['content']==pages[brain,source],'wrong raw page')
            need(r['revision']==digest(pages[brain,source].encode()),'wrong revision')
            need(r['provider_calls']==0,'provider call')
        flat=lambda groups:[word for pair in groups for word in pair]
        before=snapshot('intended')
        for token in tokens:
            pairs=[('--query',token),('--source','alpha'),('--brain','intended'),('--limit','1'),('--max-bytes','8192')]
            for i,order in enumerate(itertools.permutations(pairs)):
                argv=['memory','read',*flat(order)]
                check(f'memory/{token}/order-{i}',lambda argv=argv:mem(argv))
        for source in sources[:-1]:
            pairs=[('--source',source),('--brain','intended'),('--uri',f'qbrain://{source}/resources/docs/a'),('--layer','L2')]
            for i,order in enumerate(itertools.permutations(pairs)):
                argv=['context','read',*flat(order)]
                check(f'context/{source}/order-{i}',lambda argv=argv,source=source:ctx(argv,source=source))
        check('reads do not alter application rows',lambda:need(before==snapshot('intended'),'read mutated data'))
        for label,filebrain,environment,explicit,chosen in [
            ('default',None,None,[], 'default'),('file','configured',None,[],'configured'),
            ('environment','configured','environment',[],'environment'),('empty-env','configured','',[],'configured'),
            ('explicit','configured','environment',['--brain','intended'],'intended')]:
            c=data/'config.json'
            if filebrain is None:c.unlink(missing_ok=True)
            else:c.write_text(json.dumps({'brain_id':filebrain}))
            extra={} if environment is None else {'QBRAIN_BRAIN':environment}
            check('memory brain selection/'+label,lambda extra=extra,explicit=explicit,chosen=chosen:mem(['memory','read','--query','--brain','--source','alpha',*explicit],brain=chosen,extra=extra))
            check('context brain selection/'+label,lambda extra=extra,explicit=explicit,chosen=chosen:ctx(['context','read','--uri','qbrain://alpha/resources/docs/a','--source','alpha','--layer','L2',*explicit],brain=chosen,extra=extra))
        (data/'config.json').write_text(json.dumps({'brain_id':'intended'}))
        invalid=[
            (['memory','read','--query'],2,'invalid_cli_argument'),
            (['memory','read','--query','x','--query','y'],2,'duplicate_argument'),
            (['memory','read','--unknown','x'],2,'invalid_cli_argument'),
            (['memory','extract','--event',''],2,'event_id_required'),
            (['memory','read','--brain',''],2,'invalid brain id'),
            (['context','read','--uri'],1,'invalid_cli_argument'),
            (['context','read','--brain','new-one','--brain','new-two'],1,'invalid_cli_argument'),
            (['context','read','--source','alpha','--layer',''],1,'invalid_layer'),
            (['context','read','--max-bytes',''],1,'invalid_integer'),
            (['context','read','--brain',''],2,'invalid brain id')]
        before=snapshot('intended')
        for argv,code,error in invalid:
            def reject(argv=argv,code=code,error=error):
                r=run(argv,expected=code);need(error.encode() in r.stdout+r.stderr,'wrong rejection')
            check('reject/'+repr(argv),reject)
        check('rejections do not alter application rows',lambda:need(before==snapshot('intended'),'invalid input mutated rows'))
        def consent(brain,source):
            cfg(brain,'memory.writeback','off')
            before=snapshot(brain)
            r=obj(['memory','capture','--source',source,'--brain',brain],payload('no-consent-'+brain,'I prefer private notes.'))
            need(r.get('status')=='skipped' and r.get('archived') is False,'option value granted consent')
            need(before==snapshot(brain),'denied capture mutated data')
            r=obj(['memory','capture','--source',source,'--manual','--brain',brain],payload('yes-consent-'+brain,'I prefer explicit consent.'))
            need(r.get('status')=='archived','real manual flag broken')
        check('source named --manual is not consent',lambda:consent('intended','--manual'))
        check('brain named --manual is not consent',lambda:consent('--manual','alpha'))
        check('no unexpected brain directories',lambda:need({x.name for x in (data/'brains').iterdir()}==set(brains),'unexpected brain created'))
    report={'schema':'qbrain-n47m-separate-probe-v1','reviewer':'coordinating ChatGPT; separate self-review, not a subagent',
            'platform':platform.platform(),'binary_sha256':digest(exe.read_bytes()),'script_sha256':digest(Path(__file__).read_bytes()),
            'passed':sum(r['passed'] for r in results),'failed':sum(not r['passed'] for r in results),
            'command_count':len(commands),'checks':results,'commands':commands}
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('checks','commands')}))
    raise SystemExit(1 if report['failed'] else 0)

if __name__=='__main__':main()
