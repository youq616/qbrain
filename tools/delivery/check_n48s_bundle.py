"""Qualify the actual extracted N48S ZIP. Synthetic Windows/PG work only."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import package_n48s as p
from check_n48k_bundle import environments, child_environment

OLD_SHA="c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d"

def execute(source, bundle, package, old, output):
    p.z.need(os.name=="nt","native Windows required")
    source=p.old.regular(source,True).resolve(strict=True)
    bundle=p.old.regular(bundle,True).resolve(strict=True)
    package=p.old.regular(package).resolve(strict=True)
    old=p.old.regular(old).resolve(strict=True)
    output=output.absolute()
    p.old.regular(output.parent,True)
    p.z.need(output != source and source not in output.parents and
             output != bundle and bundle not in output.parents, "output inside input")
    p.z.need(p.old.git(source,"rev-parse","HEAD").decode().strip()==p.SOURCE,"fixed product source")
    p.z.need(p.old.git(source,"rev-parse","HEAD^{tree}").decode().strip()==p.TREE,"fixed product tree")
    original=p.old.read(package,p.z.MAX_ARCHIVE);package_hash=p.z.sha(original)
    contents=p.z.archive_files(original)
    m=p.z.obj(contents["MANIFEST.json"])
    p.z.need(m["product_source"]==p.SOURCE and m["product_tree"]==p.TREE and
             m["status"]=="BUILT_NOT_YET_ACCEPTED","candidate identity")
    # Reconstruct inputs from fixed Git source, not a self-edited bundle manifest.
    wanted=p.expected(contents["qbrain.exe"],p.source_files(source),
                      contents["START-HERE.zh-CN.md"],p.z.obj(contents["BUILD-PROVENANCE.json"]))
    p.verify(original,wanted)
    oldraw=p.old.read(old,p.z.MAX_ARCHIVE)
    p.z.need(p.z.sha(oldraw)==OLD_SHA,"old published package")
    output=output.absolute();output.mkdir(exist_ok=False);(output/"logs").mkdir()
    rows=[]
    def inventory():
        names={v.relative_to(bundle).as_posix() for v in bundle.rglob("*") if not v.is_dir()}
        p.z.need(names==set(wanted),"extracted file inventory")
        for name,raw in wanted.items():p.z.need(p.old.read(bundle/name)==raw,"extracted file bytes")
    inventory()
    exe=bundle/"qbrain.exe"
    with tempfile.TemporaryDirectory(prefix="n48s-acceptance-") as tmp:
        build_env,runtime=environments(os.environ,tmp)
        # PG integration receives only the dedicated workflow variables.
        pg_env={**runtime}
        for key in ("QBRAIN_PG_HOOK_PROCESS_DSN","QBRAIN_PG_HOOK_EMPTY_DSN","QBRAIN_PG_HOOK_TEST_DISPOSABLE"):
            if key in os.environ:pg_env[key]=os.environ[key]
        p.z.need(pg_env.get("QBRAIN_PG_HOOK_TEST_DISPOSABLE")=="1","disposable PG required")
        def run(name,args,*,env=None,cwd=bundle,data=None,code=0):
            argv=list(map(str,args));child,reset=child_environment(argv,env or runtime)
            row=dict(name=name,argv=argv,status="started",expected_exit=code);rows.append(row)
            (output/"driver.json").write_bytes(p.z.encoded(dict(package_sha256=package_hash,steps=rows)))
            result=subprocess.run(argv,env=child,cwd=cwd,input=data,capture_output=True,timeout=1800)
            for ext,raw in (("stdout",result.stdout),("stderr",result.stderr)):
                (output/"logs"/(name+"."+ext)).write_bytes(raw)
                row[ext+"_sha256"]=p.z.sha(raw)
            if data is not None:(output/"logs"/(name+".stdin")).write_bytes(data)
            row.update(status="completed",exit=result.returncode)
            (output/"driver.json").write_bytes(p.z.encoded(dict(package_sha256=package_hash,steps=rows)))
            p.z.need(result.returncode==code,"failed stage "+name)
            return result
        def suite(name,args,count,cwd=bundle):
            result=run(name,args,cwd=cwd)
            text=(result.stdout+result.stderr).decode("utf-8-sig")
            p.z.need(re.search(r"Ran "+str(count)+r" tests in ",text) and
                     re.search(r"\nOK\s*$",text),"suite inventory "+name)
        clean={**runtime,"PATH":str(Path(os.environ["SystemRoot"])/"System32")}
        run("system-only-init",[exe,"init","--no-default","--brain","n48s-system-only"],env=clean)
        run("system-only-cost",[exe,"cost","compare"],env=clean,
            data=contents["examples/cost/compare-basic.json"])
        p.z.need(not list(bundle.rglob("*.dll")),"unexpected bundled DLL")
        for mode in ("normal","optimized"):
            py=[sys.executable]+(["-O"] if mode=="optimized" else [])
            suite("evaluation-"+mode,py+[bundle/"tools/acceptance/test_model_evaluation.py",
                  "--binary",exe,"--evidence",output/("evaluation-"+mode)],28)
            suite("cost-bridge-"+mode,py+[bundle/"tools/acceptance/test_model_cost.py",
                  "--binary",exe,"--evidence",output/("cost-bridge-"+mode)],27)
            suite("old-acceptance-"+mode,py+["-m","unittest","-v","test_memory_tasks",
                  "test_memory_metrics","test_model_ab","test_model_projection","test_model_framing"],
                  48,cwd=bundle/"tools/acceptance")
            for test in ("sqlite_backup","sqlite_check"):
                dest=output/(test+"-"+mode)
                run(test+"-"+mode,py+[source/".ci"/("test_"+test+".py"),"--binary",exe,"--output",dest],env=clean)
                run(test+"-verify-"+mode,py+[source/".ci"/("test_"+test+".py"),"--binary",exe,"--output",dest,"--verify"],env=clean)
            run("postgres-hooks-"+mode,py+[source/".ci/test_pg_hooks.py","--binary",exe,
                "--output",output/("postgres-hooks-"+mode)],env=pg_env)
        baseline=output/"baseline";baseline.mkdir()
        # Exact original published archive was independently pinned above.
        for name,raw in p.z.archive_files(oldraw).items():
            dest=baseline/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
        template=p.old.read(source/"tools/delivery/test_n48k_upgrade.ps1")
        prior=b"24345f85e0c4962c93205a7fab0fbdb380a5ff09"
        p.z.need(template.count(prior)==1,"upgrade template source identity")
        executed=template.replace(prior,p.SOURCE.encode())
        upgrade_script=output/"test_n48s_upgrade.ps1"
        upgrade_script.write_bytes(executed)
        (output/"upgrade-template-binding.json").write_bytes(p.z.encoded(dict(
            original_sha256=p.z.sha(template),executed_sha256=p.z.sha(executed),
            replacement="product SHA only; every existing assertion unchanged",
            before=prior.decode(),after=p.SOURCE)))
        for shell in ("powershell","pwsh"):
            prefix=[shell,"-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File"]
            for test in ("test_installer_snapshot","test_installer_recovery"):
                run(test+"-"+shell,prefix+[source/".ci"/(test+".ps1"),"-Binary",exe,
                    "-Installer",bundle/"scripts/Install-QbrainMemory.ps1",
                    "-Report",output/(test+"-"+shell+".json")])
            run("upgrade-"+shell,prefix+[upgrade_script,
                "-OldPackage",old,"-NewPackage",package,"-ExpectedNewSha256",package_hash,
                "-Report",output/("upgrade-"+shell+".json")])
            # Reuse the unchanged preservation assertions with an explicitly new
            # package identity. Do not emit the old helper's fixed N48K ZIP hash.
            code=("import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);"
                  "import test_n48k_existing_receipts as t;t.NEW_SHA=sys.argv[2];"
                  "r=t.exercise(*[Path(x) for x in sys.argv[3:7]],sys.argv[7],Path(sys.argv[8]));"
                  "print(t.encode({k:v for k,v in r.items() if k not in ('checks','calls')}).decode())")
            run("existing-receipts-"+shell,[sys.executable,"-c",code,source/".ci",package_hash,
                baseline/"qbrain.exe",exe,baseline/"scripts/Install-QbrainMemory.ps1",
                bundle/"scripts/Install-QbrainMemory.ps1",shell,output/("existing-receipts-"+shell)])
            r=p.z.obj((output/("existing-receipts-"+shell)/"RESULT.json").read_bytes())
            p.z.need(r["result"]=="PASS" and r["package_sha256"]==package_hash and
                     all(c["passed"] is True for c in r["checks"]),"receipt preservation")
        run("retained55",[sys.executable,source/".ci/run_n48i_checks.py","--binary",exe,
            "--baseline",baseline/"qbrain.exe","--output",output/"retained"],env=build_env,cwd=source)
        inventory()
        p.z.need(p.old.read(package,p.z.MAX_ARCHIVE)==original,"ZIP changed")
    result=dict(schema="qbrain-n48s-acceptance-v1",result="PASS_BOUNDED_WINDOWS_CANDIDATE",
        package_sha256=package_hash,package_bytes=len(original),binary_sha256=p.z.sha(contents["qbrain.exe"]),
        product_source=p.SOURCE,product_tree=p.TREE,stages=len(rows),dependencies=p.dependencies(contents["qbrain.exe"]),
        native_platform="windows",powershell_majors=[5,7],postgres_tests_executed=True,
        package_unchanged=True,extracted_inventory_unchanged=True,
        real_client_consumption_verified=False,real_model_quality_verified=False,
        stable_release=False,signed=False,issue40_closed=False,full_project_complete=False)
    (output/"ACCEPTANCE.json").write_bytes(p.z.encoded(result))
    return result

if __name__=="__main__":
    a=argparse.ArgumentParser(description=__doc__)
    for n in ("source","bundle","package","old","output"):a.add_argument("--"+n,type=Path,required=True)
    args=a.parse_args()
    print(p.z.encoded(execute(args.source,args.bundle,args.package,args.old,args.output)).decode(),end="")
