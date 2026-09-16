"""Outcome-only differential corpus; does not alter product source or execute a host."""
from __future__ import annotations
import argparse, collections, hashlib, json, math, random, subprocess
from pathlib import Path

SEED=4712026
class Object:
    def __init__(self,pairs): self.pairs=pairs

def expected(raw:bytes)->bool:
    if len(raw)>1048576 or b'\x00' in raw:return False
    try:
        text=raw.decode('utf-8-sig')
        def constant(_):raise ValueError('non-JSON number')
        value=json.loads(text,object_pairs_hook=Object,parse_constant=constant)
        def scalar_string(s):return all(not 0xd800<=ord(c)<=0xdfff for c in s)
        def walk(v,depth):
            if depth>32:return False
            if isinstance(v,Object):
                keys=[k for k,_ in v.pairs]
                if len(set(keys))!=len(keys):return False
                return all(depth+1<=32 and scalar_string(k) and walk(item,depth+1) for k,item in v.pairs)
            if isinstance(v,list):return all(walk(item,depth+1) for item in v)
            if isinstance(v,str):return scalar_string(v)
            if isinstance(v,float):return math.isfinite(v)
            if type(v) is int and not -(1<<63)<=v<=(1<<64)-1:
                try:return math.isfinite(float(v))
                except OverflowError:return False
            return True
        return walk(value,0)
    except (ValueError,UnicodeError,RecursionError):return False

def corpus():
    rng=random.Random(SEED);rows=[]
    keys=['a','A','source_id','😀','中文','a\0b','é','e\u0301','/slash','~','quoted"','back\\slash']
    def emit(v):
        if isinstance(v,Object):return '{'+','.join(json.dumps(k,ensure_ascii=rng.choice([True,False]))+':'+emit(item) for k,item in v.pairs)+'}'
        if isinstance(v,list):return '['+','.join(emit(x) for x in v)+']'
        return json.dumps(v,ensure_ascii=rng.choice([True,False]),separators=(',',':'))
    def node(depth=0):
        kind=rng.randrange(6) if depth<5 else rng.randrange(3)
        if kind<3:return rng.choice([None,True,False,0,-123,1.25,'中文😀','escaped\0','{"same":0,"same":1}', '\\u0061'])
        if kind==3:return [node(depth+1) for _ in range(rng.randrange(4))]
        chosen=rng.sample(keys,rng.randrange(4))
        return Object([(k,node(depth+1)) for k in chosen])
    def add(label,raw):
        if isinstance(raw,str):raw=raw.encode('utf-8')
        assert b'\n' not in raw,'one physical line per parser invocation'
        rows.append((label,raw,expected(raw)))
    for i in range(1800):
        v=node();text=emit(v);add('generated_unique',text)
        k=rng.choice(keys)
        duplicate=Object([(k,v),(k,node())]);add('generated_duplicate',emit(duplicate))
        add('nested_duplicate',emit(Object([('outer',[node(),duplicate,node()])])) )
        add('siblings_not_duplicates',emit([Object([(k,v)]),Object([(k,node())])]))
    for depth in range(0,41):
        for kind in ('array','object','mixed'):
            for leaf in ('0','{}','[]','{"x":0}'):
                v=leaf
                for n in range(depth):v='['+v+']' if kind=='array' or (kind=='mixed' and n%2) else '{"k":'+v+'}'
                add('depth_boundary',v)
    fixed=[b'',b' ',b'\r',b'{',b'{} {}',b'{}\0',b'{\0}',b'\0{}',b'"a\0b"',b'{"x":NaN}',b'Infinity',b'1e999',b'1e308',b'-1e999',b'01',b'+1',b'1.',b'{}\xef\xbb\xbf',b'\xef\xbb\xbf{}',b' \xef\xbb\xbf{}',b'{"x":"\xff"}',b'{"x":"\xc0\x80"}',b'{"x":"\xed\xa0\x80"}',b'{"x":"\\ud800"}',b'{"x":"\\udc00"}',b'{"x":"\\ud83d\\ude00"}',b'{"a\\u0000b":1,"a":2}',b'{"\\u0061":1,"a":2}',b'{"k":[{"k":0},{"k":1}],"other":true}',b'[{}, {"k":1,"k":1}]']
    for raw in fixed:add('handwritten_boundaries',raw)
    for n in (1048575,1048576,1048577):add('byte_boundary',b'"'+b'x'*(n-2)+b'"')
    for scalar in (0x00,0x01,0x1f,0x20,0x22,0x5c,0x7f,0x80,0x800,0xd7ff,0xe000,0xffff,0x10000,0x10ffff):
        k=chr(scalar)
        for escaped in (False,True):
            key=json.dumps(k,ensure_ascii=escaped)
            add('unicode_key', '{'+key+':0}')
            alternate=json.dumps(k,ensure_ascii=not escaped)
            add('unicode_duplicate','{'+key+':0,'+alternate+':1}')
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    rows=corpus();input_bytes=b'\n'.join(raw for _,raw,_ in rows)+b'\n'
    proc=subprocess.run([str(a.binary.resolve()),'--parse-lines'],input=input_bytes,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
    observations=[json.loads(line) for line in proc.stdout.splitlines()]
    errors=[]
    if proc.returncode or len(observations)!=len(rows):errors.append({'process_exit':proc.returncode,'expected_rows':len(rows),'actual_rows':len(observations)})
    for i,((label,raw,expect),actual) in enumerate(zip(rows,observations)):
        if actual!={'accepted':expect}:errors.append({'index':i,'label':label,'sha256':hashlib.sha256(raw).hexdigest(),'expected':expect,'actual':actual})
    report={'result':'PASS' if not errors else 'FAIL','seed':SEED,'cases':len(rows),'oracle_accept':sum(e for _,_,e in rows),'oracle_reject':sum(not e for _,_,e in rows),'categories':dict(collections.Counter(label for label,_,_ in rows)),'input_sha256':hashlib.sha256(input_bytes).hexdigest(),'binary_sha256':hashlib.sha256(a.binary.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'process_exit':proc.returncode,'stderr_bytes':len(proc.stderr),'mismatches':errors,'scope':'Generated raw JSON against independent Python object-pairs/Unicode/depth/number oracle; Linux parser probe, not live client or all-input correctness proof'}
    a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report));return 0 if not errors else 1
if __name__=='__main__':raise SystemExit(main())
