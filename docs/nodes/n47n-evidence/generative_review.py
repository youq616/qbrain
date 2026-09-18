"""Separately authored grammar-generation review; same coordinator, not subagent.

Expected objects are constructed from generated semantic inputs, NOT computed
by running a copy of the production parsing loop. Fixed seed; no network/data.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess


def build_cases():
    rng = random.Random(470014)
    flags = ['--json','--no-vector','--rerank','--rerank-llm']
    values = {
        '--brain': ['intended','--json','--','--query=x','with_underscore'],
        '--limit': ['','-2147483648','2147483647','+1','-0','0005','-0001','101'],
        '--mode': ['','balanced','conservative','tokenmax'],
    }
    literal = ['--','--brain','--limit','--mode','--rerank','--rerank-llm',
               '--json','--query','--query=','--no-vector','--source',
               '--brain sentinelneedle','中文😀',' x\t y\r\n','a=b=c','-h',
               'alpha  beta','--unknown','--brain=decoy','-- --json']
    cases = []
    def add(argv, expected, kind):
        cases.append({'argv':argv,'expected':expected,'kind':kind})
    def expected(query, selected, enabled):
        return {'query':query,'values':selected,'flags':sorted(enabled),
                'brain_args':['--brain',selected['--brain']] if '--brain' in selected else []}
    for _ in range(2400):
        selected = {key:rng.choice(opts) for key,opts in values.items() if rng.randrange(2)}
        enabled = rng.sample(flags, rng.randrange(5))
        groups = [[flag] for flag in enabled]
        for key,value in selected.items():
            if value.startswith('--') or rng.randrange(2): groups.append([key+'='+value])
            else: groups.append([key,value])
        query = rng.choice(literal)
        form = rng.randrange(3)
        if form < 2:
            group = ['--query',query] if form == 0 else ['--query='+query]
            groups.append(group)
            rng.shuffle(groups)
            want = dict(selected); want['--query'] = query
            argv = sum(groups,[])
            add(argv,expected(query,want,enabled),'explicit')
            add(argv+['--unknown'],{'error':'invalid_search_argument'},'unknown')
            add(argv+['extra'],{'error':'mixed_search_query'},'mixed')
            add(argv+['--query=duplicate'],{'error':'duplicate_search_argument'},'duplicate-query')
        else:
            rng.shuffle(groups)
            words = [query, '--', rng.choice(literal)]
            argv = sum(groups,[])+['--']+words
            add(argv,expected(' '.join(words).strip(' \t\r\n\v\f'),selected,enabled),'delimiter')
            # Adding option-like text AFTER -- must stay data, not error/control.
            add(argv+['--brain','decoy'],expected((' '.join(words)+' --brain decoy').strip(' \t\r\n\v\f'),selected,enabled),'delimiter-tail')
        # Missing values and malformed controls are checked with an unambiguous seed.
        key = rng.choice(list(values))
        add(['--query',query,key],{'error':'missing_search_value'},'missing')
        add(['--query',query,key,'--json'],{'error':'missing_search_value'},'missing-before-flag')
        flag = rng.choice(flags)
        add(['--query',query,flag+'=true'],{'error':'invalid_search_argument'},'flag-equals')
        add(['--query',query,flag,flag],{'error':'duplicate_search_argument'},'duplicate-flag')
    # Ordinary positional joining with real options interleaved. Construct the
    # expected query from the words chosen before inserting the option groups.
    for _ in range(1200):
        words = [rng.choice(['alpha','beta','中文','', ' ', '  x ', '-h', '\t'])
                 for _ in range(rng.randrange(1, 9))]
        if not ''.join(words).strip(' \t\r\n\v\f'):
            words.append('required')
        first = next(i for i,word in enumerate(words) if word != '')
        query = ' '.join(words[first:]).strip(' \t\r\n\v\f')
        selected = {'--brain':'intended','--limit':'2'}
        enabled = rng.sample(flags, rng.randrange(5))
        groups = [[word] for word in words]
        for pair in [['--brain','intended'],['--limit=2'],*[[f] for f in enabled]]:
            groups.insert(rng.randrange(len(groups)+1),pair)
        add(sum(groups,[]),expected(query,selected,enabled),'ordinary-join')
    for text in ['+','-','+-1','++1','--1','1x','1.0','1e2','0x10',' 5','5 ',
                 '2147483648','-2147483649','９','+ 1','\t','9'*100]:
        add(['--query=x','--limit='+text],{'error':'invalid_search_limit'},'invalid-number')
    for text in ['BALANCED','bogus','balanced ','--json','0']:
        add(['--query=x','--mode='+text],{'error':'invalid_search_mode'},'invalid-mode')
    for argv in [[],['--'],['--query='],['--query','\t \n'],['--json','--no-vector'],['--',' ']]:
        add(argv,{'error':'search_query_required'},'empty')
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args = parser.parse_args()
    probe = args.probe.resolve(strict=True)
    cases = build_cases()
    payload = b''.join((json.dumps(case['argv'],ensure_ascii=False)+'\n').encode('utf-8') for case in cases)
    result = subprocess.run([str(probe)],input=payload,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
    output = result.stdout.splitlines()
    if result.returncode or len(output) != len(cases):
        raise RuntimeError(f'probe failed {result.returncode}: {len(output)}/{len(cases)} responses; '+result.stderr.decode(errors='replace'))
    failures = []
    categories = {}
    for index,(case,line) in enumerate(zip(cases,output)):
        observed=json.loads(line)
        categories[case['kind']]=categories.get(case['kind'],0)+1
        if observed != case['expected']:
            failures.append({'index':index,**case,'observed':observed})
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    report={'schema':'qbrain-n47n-generative-review-v1','seed':470014,'checks':len(cases),
            'passed':len(cases)-len(failures),'failed':len(failures),'categories':categories,
            'probe_sha256':sha(probe.read_bytes()),'generator_sha256':sha(Path(__file__).read_bytes()),
            'input_sha256':sha(payload),'output_sha256':sha(result.stdout),
            'stderr':result.stderr.decode('utf-8',errors='replace'),'failures':failures,
            'limits':['pure production parser adapter; not full product execution','same coordinator self-review','generated overlaps are not distinct capabilities']}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['failures','limits']}))
    raise SystemExit(bool(failures))

if __name__=='__main__': main()
