"""Real-process regression: project-local config writes must not retarget defaults."""
from pathlib import Path
from contextlib import closing
import argparse
import os
import sqlite3
import subprocess
import tempfile

p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True)
binary=p.parse_args().binary.resolve(strict=True)
with tempfile.TemporaryDirectory(prefix='qbrain-local-config-') as t:
    root=Path(t);env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
    env.update(HOME=t,USERPROFILE=t,LOCALAPPDATA=t)
    def run(*args):
        return subprocess.run([str(binary),*args],env=env,cwd=root,check=True,capture_output=True,timeout=15).stdout.decode('utf-8')
    run('init','--brain','original')
    data=root if os.name=='nt' else root/'.local/share'
    config=data/'Qbrain/config.json';original=config.read_bytes()
    run('init','--brain','project','--no-default')
    assert config.read_bytes()==original
    run('config','set','memory.writeback','salient','--brain','project','--local')
    assert config.read_bytes()==original
    assert run('config','get','memory.writeback','--brain','project').strip()=='salient'
    run('config','set','context.external_summary','allow','--brain','project','--local')
    assert config.read_bytes()==original
    assert run('config','get','context.external_summary','--brain','project').strip()=='allow'
    with closing(sqlite3.connect(data/'Qbrain/brains/original/brain.db')) as db:
        assert db.execute("SELECT COUNT(*) FROM config WHERE key IN ('memory.writeback','context.external_summary')").fetchone()[0]==0
    print('Local config integration: 6 checks passed; default file and other brain unchanged.')
