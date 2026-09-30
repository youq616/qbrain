"""Actual CLI acceptance for scoped recursive directory search; disposable SQLite only."""
from pathlib import Path
import argparse, json, os, subprocess, tempfile, hashlib

def run(binary, output):
    binary=binary.resolve(strict=True)
    output.mkdir(parents=True,exist_ok=False)
    commands=[]; checks=[]
    def need(ok,label):
        checks.append({"name":label,"passed":bool(ok)})
        if not ok: raise ValueError(label)
    clean={k:v for k,v in os.environ.items()
           if not k.upper().startswith(("QBRAIN","PG","OPENAI","ANTHROPIC","GH_TOKEN","GITHUB_TOKEN"))}
    with tempfile.TemporaryDirectory(prefix="n48z-dir-") as tmp:
        env={**clean,"HOME":tmp,"USERPROFILE":tmp,"LOCALAPPDATA":tmp,"APPDATA":tmp,
             "QBRAIN_EMBED_MOCK":"1"}
        def call(args,code=0):
            p=subprocess.run([str(binary),*args,"--brain","n48z"],cwd=tmp,env=env,
                             capture_output=True,timeout=30)
            commands.append({"args":args,"exit":p.returncode,
              "stdout_sha256":hashlib.sha256(p.stdout).hexdigest(),
              "stderr_sha256":hashlib.sha256(p.stderr).hexdigest()})
            need(p.returncode==code,"exit "+str(args))
            return p
        call(["init","--no-default"])
        call(["config","set","embed.auto","false","--local"])
        pages=[
          ("docs/a","Needle A","needle root","note"),
          ("docs/sub/b","Nested","needle nested","note"),
          ("docs-neighbor/c","Neighbor","needle outside","note"),
          ("docs/tool","Tool","needle skill","skill"),
        ]
        for slug,title,body,kind in pages:
            path=Path(tmp)/(slug.replace("/","_")+".txt")
            path.write_text(body,encoding="utf8")
            call(["put","--slug",slug,"--title",title,"--type",kind,"--file",str(path)])
        scoped=json.loads(call(["search","--query","needle","--uri",
            "qbrain://default/resources/docs/","--no-vector","--json"]).stdout)
        need({x["slug"] for x in scoped}=={"docs/a","docs/sub/b"},
             "CLI recursively scoped resources")
        root=json.loads(call(["search","--query","needle","--uri",
            "qbrain://default/resources/","--no-vector","--json"]).stdout)
        need("docs-neighbor/c" in {x["slug"] for x in root},
             "root includes recursive sibling")
        skills=json.loads(call(["search","--query","needle","--uri",
            "qbrain://default/skills/docs/","--no-vector","--json"]).stdout)
        need([x["slug"] for x in skills]==["docs/tool"],"CLI namespace isolated")
        vector=json.loads(call(["search","--query","needle","--uri",
            "qbrain://default/resources/docs/","--json"]).stdout)
        need({x["slug"] for x in vector}=={"docs/a","docs/sub/b"},
             "CLI vector-enabled scope stays bounded")
        bad=call(["search","--query","needle","--uri",
                  "qbrain://default/resources/docs","--json"],1)
        need(b"directory_uri_required" in bad.stderr or
             b"directory_uri_required" in bad.stdout,
             "invalid directory emits explicit error")
        dup=call(["search","--query","needle","--uri",
                  "qbrain://default/resources/docs/","--uri",
                  "qbrain://default/resources/"],2)
        need(b"duplicate_search_argument" in dup.stderr or
             b"duplicate_search_argument" in dup.stdout,
             "duplicate uri rejected before brain work")
    report={"schema":"qbrain-n48z-directory-process-v1","passed":True,
            "commands":commands,"checks":checks,"command_count":len(commands),
            "check_count":len(checks),"paid_requests":0,"postgres_executed":False}
    (output/"RESULT.json").write_text(json.dumps(report,indent=2),encoding="utf8")
    print(json.dumps({k:v for k,v in report.items() if k not in ("commands","checks")}))

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--binary",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    run(a.binary,a.output)
