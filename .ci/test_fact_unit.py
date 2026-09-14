"""Execute the production FactStore suite and bind its report to source/probe bytes."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from validate_fact_report import validate_unit_report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--require-windows',action='store_true')
    a=p.parse_args()
    if a.require_windows and os.name!='nt':
        p.error('Native Windows evidence cannot use a portable test')
    binary=a.binary.resolve(strict=True)
    source=Path(__file__).resolve().parents[1]/'tests/test_n47a.cpp'
    report={'result':'FAIL','native_windows':os.name=='nt','provider_calls':False}
    try:
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        clean=subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0
        report.update(head_commit=head,source_commit=head if clean else None,tracked_tree_clean=clean,
                      binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                      test_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        with tempfile.TemporaryDirectory(prefix='qbrain-fact-unit-') as d:
            env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
            env.update(HOME=d,USERPROFILE=d,LOCALAPPDATA=d,APPDATA=d,TEMP=d,TMP=d)
            raw=Path(d)/'unit.json'
            result=subprocess.run([str(binary),'--report',str(raw)],env=env,
                capture_output=True,timeout=180)
            report['exit_code']=result.returncode
            sys.stdout.write(result.stdout.decode('utf-8',errors='replace'))
            sys.stderr.write(result.stderr.decode('utf-8',errors='replace'))
            if result.returncode!=0:
                raise RuntimeError('Fact unit process failed')
            payload=json.loads(raw.read_text(encoding='utf-8'))
        for key in ('result','scenarios','scenario_count','checks'):
            report[key]=payload[key]
        expected=re.findall(r'scenario\("([^"\r\n]+)"',source.read_text(encoding='utf-8'))
        # Dirty local runs may execute tests, but remain unattributed in reports.
        validate_unit_report(report,source_commit=report['source_commit'],
            binary_sha256=report['binary_sha256'],test_sha256=report['test_sha256'],
            expected_scenarios=expected,native=a.require_windows,require_clean=False)
    except Exception as error:
        report['result']='FAIL';report['error_type']=type(error).__name__
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return 0 if report['result']=='PASS' else 1


if __name__=='__main__':
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    raise SystemExit(main())
