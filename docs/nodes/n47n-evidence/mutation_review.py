"""Reject deliberate parser defects using the separate deterministic generator.

Mutants exist only under a temporary include directory; never change production.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(); root=args.root.resolve(strict=True); out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    header=root/'include/qbrain/cli/search_arguments.hpp'
    source=header.read_bytes();text=source.decode('utf-8')
    mutations=[
        ('ignore-unknown','throw std::invalid_argument("invalid_search_argument");','continue;'),
        ('allow-duplicates','if (!seen.insert(key).second) throw std::invalid_argument("duplicate_search_argument");','seen.insert(key);'),
        ('trim-explicit','out.query = out.value("--query");','out.query = util::trim(out.value("--query"));'),
        ('lose-second-delimiter','if (!literal && arg == "--")','if (arg == "--")'),
    ]
    rows=[]
    with tempfile.TemporaryDirectory(prefix='n47n-mutants-') as tmp:
        for name,before,after in mutations:
            modified=text.replace(before,after,1)
            if modified==text: raise ValueError('mutation not applied: '+name)
            inc=Path(tmp)/name/'qbrain/cli';inc.mkdir(parents=True)
            (inc/'search_arguments.hpp').write_text(modified,encoding='utf-8')
            exe=Path(tmp)/name/'probe'
            cmd=['g++','-std=c++20','-O1','-I'+str(inc.parents[1]),'-I'+str(root/'include'),'-I'+str(root/'third_party'),str(root/'docs/nodes/n47n-evidence/parser_probe.cpp'),str(root/'src/qbrain/util/string_util.cpp'),'-o',str(exe)]
            build=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
            if build.returncode: raise RuntimeError(build.stderr.decode())
            report=out/(name+'.json')
            run=subprocess.run(['python',str(root/'docs/nodes/n47n-evidence/generative_review.py'),'--probe',str(exe),'--report',str(report)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
            if not report.exists(): raise RuntimeError(run.stderr.decode())
            value=json.loads(report.read_text())
            if run.returncode!=1 or value['failed']<=0: raise AssertionError('mutant survived: '+name)
            rows.append({'mutation':name,'compile_exit':build.returncode,'test_exit':run.returncode,'rejected_cases':value['failed'],
                         'report_sha256':hashlib.sha256(report.read_bytes()).hexdigest(),'sample_failures':value['failures'][:2]})
    if source != header.read_bytes(): raise AssertionError('production header changed')
    result={'schema':'qbrain-n47n-mutation-review-v1','mutants_rejected':len(rows),'mutants':rows,'production_unchanged':True,
            'limits':['deliberate test defects, not newly found product vulnerabilities','same coordinator self-review']}
    (out/'SUMMARY.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({r['mutation']:r['rejected_cases'] for r in rows}))

if __name__=='__main__':main()
