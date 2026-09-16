"""Supplemental finite wide/deep/parser-recovery checks, not performance guarantees."""
from pathlib import Path
import argparse,json,subprocess,hashlib

def corpus():
    rows=[]
    def add(name,raw,expected):
        if isinstance(raw,str):raw=raw.encode('utf-8')
        rows.append((name,raw,expected))
    for n in (1,32,1024,8192,32768):
        fields=[json.dumps('key'+str(i))+':'+str(i) for i in range(n)]
        add('wide_unique_'+str(n),'{'+','.join(fields)+'}',True)
        add('late_first_duplicate_'+str(n),'{'+','.join(fields)+',"\\u006bey0":42}',False)
        add('wide_sibling_reuse_'+str(n),'[{'+','.join(fields)+'},{'+','.join(fields)+'}]',2*(2+sum(map(len,fields))+n-1)+3<=1048576)
    for n in (33,1024,65536,200000):
        add('deep_arrays_'+str(n),'['*n+'0'+']'*n,False)
    for n in (33,1024,60000):
        add('deep_objects_'+str(n),'{"x":'*n+'0'+'}'*n,False)
    fields=['"secret":0']+[json.dumps('key'+str(i))+':0' for i in range(8192)]+['"secret":1']
    for mode in ('array','object'):
        bad='{'+','.join(fields)+'}'
        add('nested_wide_late_duplicate_'+mode,'['+bad+']' if mode=='array' else '{"outer":'+bad+'}',False)
    # Every rejected row is followed by a normal row in the same process.
    out=[]
    for name,raw,ok in rows:
        out.append((name,raw,ok));out.append(('recovery_after_'+name,b'{"ok":true,"nested":[{"k":1},{"k":2}]}',True))
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    rows=corpus();data=b'\n'.join(raw for _,raw,_ in rows)+b'\n'
    proc=subprocess.run([str(a.binary.resolve()),'--parse-lines'],input=data,capture_output=True,timeout=60)
    observations=[json.loads(x) for x in proc.stdout.splitlines()]
    failures=[]
    if proc.returncode or len(observations)!=len(rows):failures.append('process exit or output count')
    for (name,raw,expected),actual in zip(rows,observations):
        if actual!={'accepted':expected}:failures.append({'case':name,'expected':expected,'actual':actual,'bytes':len(raw)})
    report={'result':'PASS' if not failures else 'FAIL','cases':len(rows),'expected_accepted':sum(v for _,_,v in rows),'expected_rejected':sum(not v for _,_,v in rows),'process_exit':proc.returncode,'stderr_bytes':len(proc.stderr),'input_sha256':hashlib.sha256(data).hexdigest(),'binary_sha256':hashlib.sha256(a.binary.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'failures':failures,'scope':'Finite wide-object/deep-input and process recovery probes, not a memory/latency guarantee'}
    a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report));return 0 if not failures else 1
if __name__=='__main__':raise SystemExit(main())
