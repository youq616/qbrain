"""Execute real multiterm unit tests; no claim of independently measured model egress."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from test_multiterm_process import provenance
from validate_multiterm_report import validate_unit_payload


def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--require-windows',action='store_true');a=p.parse_args()
    if a.require_windows and os.name!='nt':p.error('Native Windows required')
    script=Path(__file__).resolve();test=script.parents[1]/'tests/test_n47l.cpp'
    report={'result':'FAIL','native_windows':os.name=='nt','scope':'synthetic C++ multiterm tests; no live host acceptance'}
    try:
        binary=a.binary.resolve(strict=True)
        report.update(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
            script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),test_sha256=hashlib.sha256(test.read_bytes()).hexdigest())
        with tempfile.TemporaryDirectory(prefix='qbrain-multiterm-unit-') as d:
            env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
            env.update(HOME=d,USERPROFILE=d,LOCALAPPDATA=d,APPDATA=d,TEMP=d,TMP=d)
            raw=Path(d)/'unit.json'
            r=subprocess.run([str(binary),'--report',str(raw)],env=env,capture_output=True,timeout=120)
            report['exit_code']=r.returncode
            print(r.stdout.decode('utf-8',errors='replace'),end='');print(r.stderr.decode('utf-8',errors='replace'),file=sys.stderr,end='')
            if r.returncode:raise RuntimeError('unit command failed')
            data=json.loads(raw.read_text(encoding='utf-8'))
            validate_unit_payload(data)
            for key in ('result','scenarios','scenario_count','checks'):report[key]=data[key]
    except Exception as e:report.update(result='FAIL',error_type=type(e).__name__)
    report.update(provenance(script));a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 0 if report['result']=='PASS' else 1


if __name__=='__main__':
    for s in (sys.stdout,sys.stderr):
        if hasattr(s,'reconfigure'):s.reconfigure(encoding='utf-8',errors='replace')
    raise SystemExit(main())
