"""Finite new-fixture N49D wrapper controls; identical checks under python -O.

The inherited package_evidence is deliberately NOT run by these tiny controls:
its unchanged 1152 MiB reserve belongs to native CI. Both N49D packaging boundary
wrappers and the streaming consumer are exercised on newly generated tiny ZIPs.
"""
from __future__ import annotations
import copy
import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
import zipfile

import check_n49d_sources as guard
import run_n49d_qualification as q

RESULTS=[]


def check(ok, name):
    if not ok: raise ValueError(name)


def expect_failure(name, fn, message=None):
    try: fn()
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as error:
        check(message is None or message in str(error), name+': wrong failure boundary: '+str(error))
        RESULTS.append(dict(name=name,passed=True)); return
    raise ValueError('negative control unexpectedly passed: '+name)


def control(name, fn):
    fn(); RESULTS.append(dict(name=name,passed=True))


def identity(tree='2'*40):
    return dict(commit='1'*40,tree=tree,run_id='17',run_attempt='2',job_key='linux-cmake',job_label='linux-cmake')


def source_controls():
    header=b'#include "qbrain/search/hybrid.hpp"\n'
    first=b'void register_search_ops() {\n'
    search=b'  register_one(\n      "search", Scope::Read, [](OpContext& ctx) {'
    end=b'  register_one(\n      "think", Scope::Read, [](OpContext& ctx) {'
    before={guard.HANDLERS:header+first+search+b' old; });\n'+end+b' fixed; }\n',
            guard.SERVER:b'prefix\n    json arguments = params.contains("arguments") ? params["arguments"] : json::object();\nfixed tail\n',
            guard.LEDGER:b'| search | **implemented** | old note |\n', 'inherited.txt':b'constant\n'}
    after=dict(before)
    after[guard.HANDLERS]=before[guard.HANDLERS].replace(header,header+b'#include "qbrain/search/directory.hpp"\n').replace(b' old;',b' scoped;')
    inserted=(b'    if (name == "search" && arguments.is_object() && arguments.contains("uri") &&\n'
              b'        !arguments["uri"].is_string()) {\n'
              b'      return make_tool_argument_error(id, "uri", "string value required");\n'
              b'    }\n')
    after[guard.SERVER]=before[guard.SERVER].replace(b'fixed tail\n',inserted+b'fixed tail\n')
    after[guard.LEDGER]=b'| search | **implemented** | candidate note |\n'
    mapping=lambda values:{p:('100644',guard.blob(v)) for p,v in values.items()}
    def validate(values=after, **kwargs):
        return guard.validate_delta(mapping(before),mapping(values),before.__getitem__,values.__getitem__,require_complete=False,**kwargs)
    control('source-valid-regions',validate)
    expect_failure('wrong-base',lambda:validate(base_commit='0'*40))
    expect_failure('wrong-base-tree',lambda:validate(base_tree='0'*40))
    for name,path,data in [('changed-inherited','inherited.txt',b'changed'),('extra-file','extra.txt',b'new'),
                           ('outside-handler-region',guard.HANDLERS,after[guard.HANDLERS]+b'outside'),
                           ('outside-server-region',guard.SERVER,after[guard.SERVER]+b'outside')]:
        changed=dict(after);changed[path]=data
        expect_failure(name,lambda changed=changed:validate(changed))
    deleted=dict(after);del deleted['inherited.txt']
    expect_failure('deleted-inherited',lambda:validate(deleted))
    base_index=mapping(before)
    stage_row=lambda path,value,stage=0:(value[0]+' '+value[1]+' '+str(stage)+'\t'+path).encode()+b'\0'
    encoded=b''.join(stage_row(path,value) for path,value in base_index.items())
    control('stage-zero-index-valid',lambda:check(guard.stage_zero_index(encoded)==base_index,'index preservation'))
    staged=dict(base_index);staged['.ci/run_n49d_qualification.py']=('100644',guard.blob(b'new staged fixture'))
    control('staged-added-path-retained',lambda:check('.ci/run_n49d_qualification.py' in guard.precommit_index(base_index,staged,set()),'staged addition omitted'))
    expect_failure('unmerged-index-rejected',lambda:guard.stage_zero_index(stage_row('inherited.txt',base_index['inherited.txt'],2)), 'unmerged index entry')
    extra_index=dict(staged);extra_index['unexpected.txt']=('100644',guard.blob(b'extra'))
    expect_failure('staged-extra-path-rejected',lambda:guard.precommit_index(base_index,extra_index,set()), 'unreviewed staged/untracked added file')
    deleted_index=dict(base_index);del deleted_index['inherited.txt']
    expect_failure('staged-deletion-rejected',lambda:guard.precommit_index(base_index,deleted_index,set()), 'staged inherited file deleted')
    changed_mode=dict(base_index);changed_mode['inherited.txt']=('100755',base_index['inherited.txt'][1])
    expect_failure('staged-mode-change-rejected',lambda:guard.precommit_index(base_index,changed_mode,set()), 'staged inherited mode changed')
    changed_new_mode=dict(staged);changed_new_mode['.ci/run_n49d_qualification.py']=('100755',staged['.ci/run_n49d_qualification.py'][1])
    expect_failure('staged-new-mode-rejected',lambda:guard.precommit_index(base_index,changed_new_mode,set()), 'staged new file mode unsupported')
    changed_blob=dict(base_index);changed_blob['inherited.txt']=('100644',guard.blob(b'changed staged bytes'))
    expect_failure('staged-inherited-change-rejected',lambda:guard.precommit_index(base_index,changed_blob,set()), 'staged inherited identity changed')
    raw=b'one\ntwo\n'; oid=guard.blob(raw)
    control('canonical-bytes',lambda:check(guard.checkout_bytes(raw,oid)==raw,'canonical'))
    control('whole-file-windows-newlines',lambda:check(guard.checkout_bytes(raw.replace(b'\n',b'\r\n'),oid,True)==raw,'CRLF'))
    expect_failure('mixed-newlines',lambda:guard.checkout_bytes(b'one\r\ntwo\n',oid,True))
    expect_failure('changed-with-newlines',lambda:guard.checkout_bytes(b'one\r\nthree\r\n',oid,True))


def recorder_controls(root):
    ident=identity(); binary=root/'fixture.bin';binary.write_bytes(b'fixture-binary')
    def recorder(label, required=('tiny',)):
        return q.Recorder(root/label,ident,required,dict(os.environ),root,stream_cap=2048)
    good=recorder('record-valid')
    good.run('tiny',[sys.executable,'-c','print("tiny fixture")'],2,binaries=[binary])
    binding=dict(size=1,sha256='3'*64)
    good.finish(binding,binding)
    control('recorder-valid',lambda:q.validate_recordings(lambda p:(good.root/p).read_bytes(),ident,['tiny']))
    for label,command,timeout in [('nonzero-child',[sys.executable,'-c','raise SystemExit(7)'],2),
            ('bounded-timeout',[sys.executable,'-c','import time; time.sleep(2)'],.05),
            ('output-budget',[sys.executable,'-c','print("x"*4096)'],2)]:
        r=recorder(label)
        expect_failure(label,lambda r=r,command=command,timeout=timeout:r.run('tiny',command,timeout))
        result=json.loads((r.root/'stages/tiny/result.json').read_text())
        check(result['classification']!='passed','child failure must remain failed')
    missing=recorder('missing-stage',('tiny','missing'))
    missing.run('tiny',[sys.executable,'-c','pass'],2)
    expect_failure('missing-stage',lambda:missing.finish(binding,binding))
    expect_failure('duplicate-stage',lambda:good.run('tiny',[sys.executable,'-c','pass'],2))
    data={p.relative_to(good.root).as_posix():p.read_bytes() for p in good.root.rglob('*') if p.is_file()}
    reported=recorder('requested-report');report=reported.root/'report.json'
    reported.run('tiny',[sys.executable,'-c','from pathlib import Path; Path('+repr(str(report))+').write_text("{}")'],2,reports=[report])
    reported.finish(binding,binding)
    omitted={p.relative_to(reported.root).as_posix():p.read_bytes() for p in reported.root.rglob('*') if p.is_file()}
    del omitted['report.json'];record=json.loads(omitted['stages/tiny/result.json']);record['reports']={};omitted['stages/tiny/result.json']=json.dumps(record).encode()
    expect_failure('genuine-requested-report-map-omission',lambda:q.validate_recordings(omitted.__getitem__,ident,['tiny']), 'requested report inventory mismatch')

    for name,path in [('missing-stdout','stages/tiny/stdout.bin'),('missing-stderr','stages/tiny/stderr.bin'),('missing-result-report','stages/tiny/result.json')]:
        incomplete=dict(data);del incomplete[path]
        expect_failure(name,lambda incomplete=incomplete:q.validate_recordings(incomplete.__getitem__,ident,['tiny']))
    swapped=copy.deepcopy(ident);swapped['commit']='4'*40
    expect_failure('swapped-candidate',lambda:q.validate_recordings(data.__getitem__,swapped,['tiny']))
    mutated=dict(data);stage=json.loads(mutated['stages/tiny/result.json']);stage['binaries_after'][str(binary)]['sha256']='f'*64
    mutated['stages/tiny/result.json']=json.dumps(stage).encode()
    expect_failure('swapped-binary',lambda:q.validate_recordings(mutated.__getitem__,ident,['tiny']))
    expect_failure('source-mutation-after-capture',lambda:good.finish(binding,dict(size=2,sha256='4'*64)))
    diagnostic=q.failure_diagnostics(good.root,root/'diagnostic.json',ident,['tiny'],['tiny'],'synthetic failure')
    saved=diagnostic['files']['stages/tiny/stdout.bin']
    check(base64.b64decode(saved['data'])==data['stages/tiny/stdout.bin'] and not saved['truncated'] and diagnostic['passed'] is False,
          'exact partial raw diagnostics')
    RESULTS.append(dict(name='failure-diagnostics-exact-bytes',passed=True))
    (good.root/'stages/tiny/stdout.bin').write_bytes(bytes(range(256))*300)
    diagnostic=q.failure_diagnostics(good.root,root/'diagnostic-bounded.json',ident,['tiny'],['tiny'],'synthetic bounded failure')
    saved=diagnostic['files']['stages/tiny/stdout.bin']
    check(saved['truncated'] and saved['size']==76800 and saved['retained_bytes']==65536 and
          saved['sha256']==q.digest(good.root/'stages/tiny/stdout.bin') and (root/'diagnostic-bounded.json').stat().st_size<=256*1024,
          'bounded partial diagnostics')
    RESULTS.append(dict(name='failure-diagnostics-bounded-truncation',passed=True))
    binary.write_bytes(b'changed')
    expect_failure('binary-mutation-after-capture',lambda:good.finish(binding,binding))


def audit_launch_controls():
    # Pure callbacks model CPython's payloads; this is not Windows execution.
    argv=['C:\\Program Files\\Python\\python.exe','space argument\\','embedded"quote','trailing\\','','\u4e2d\u6587']
    windows=subprocess.list2cmdline(argv)
    with patch.object(q,'_ACTIVE_OWNER',object()),patch.object(q,'_LAUNCH_THREAD',q.threading.get_ident()),patch.object(q,'_LAUNCH_ARGV',argv):
        with patch.object(q.os,'name','nt'):
            control('windows-audit-exact-quoted-command',lambda:q._audit_launch('subprocess.Popen',(argv[0],windows,None,None)))
            for index in range(len(argv)):
                changed=list(argv);changed[index]+='changed'
                expect_failure('windows-audit-changed-argument-'+str(index),lambda changed=changed:q._audit_launch('subprocess.Popen',(changed[0],subprocess.list2cmdline(changed),None,None)),'unmanaged process launch')
            expect_failure('windows-audit-wrong-payload-type',lambda:q._audit_launch('subprocess.Popen',(argv[0],argv,None,None)),'unmanaged process launch')
            with patch.object(q,'_LAUNCH_THREAD',-1):
                expect_failure('windows-audit-wrong-launch-thread',lambda:q._audit_launch('subprocess.Popen',(argv[0],windows,None,None)),'unmanaged process launch')
        with patch.object(q.os,'name','posix'):
            control('posix-audit-exact-argv',lambda:q._audit_launch('subprocess.Popen',(argv[0],argv,None,None)))
            expect_failure('posix-audit-command-string-rejected',lambda:q._audit_launch('subprocess.Popen',(argv[0],windows,None,None)),'unmanaged process launch')
            expect_failure('posix-audit-changed-command',lambda:q._audit_launch('subprocess.Popen',(argv[0],argv+['changed'],None,None)),'unmanaged process launch')


def proc_reader_controls():
    if os.name=='nt':return
    pid=os.getpid();fields=['S',str(pid),'0','0','0','0','0','0','0','0','0','0','0','0','0','0','0','0','0','123']
    raw=lambda n,comm='unusual ) comm with spaces':str(n)+' ('+comm+') '+' '.join(fields)
    control('proc-stat-unusual-comm',lambda:check(q._parse_proc_stat(raw(7),7)['start']==123,'comm parsing'))
    expect_failure('proc-stat-pid-mismatch',lambda:q._parse_proc_stat(raw(7),8),'PID/comm mismatch')
    expect_failure('proc-stat-malformed',lambda:q._parse_proc_stat('7 (x) S 1',7),'incomplete proc stat')
    with patch.object(q,'_PROC_RECORD_CAP',8):expect_failure('proc-stat-size-cap',lambda:q._parse_proc_stat(raw(7),7),'record cap')
    with tempfile.TemporaryDirectory(prefix='n49d-proc-read-') as tmp:
        path=Path(tmp)/'stat';text=raw(7,comm='\u00e9');data=text.encode('utf-8');path.write_bytes(data)
        control('proc-read-multibyte-at-byte-cap',lambda:check(q._parse_proc_stat(q._proc_read(path,len(data)),7)['start']==123,'multibyte byte boundary'))
        expect_failure('proc-read-multibyte-over-byte-cap',lambda:q._proc_read(path,len(text)),'proc record byte cap')
        with patch.object(q,'_PROC_RECORD_CAP',len(text)):
            expect_failure('proc-stat-multibyte-over-byte-cap',lambda:q._parse_proc_stat(text,7),'record cap')
        path.write_bytes(b'\xff')
        expect_failure('proc-read-strict-decoding',lambda:q._proc_read(path,1),'decode')
        path.write_bytes(b'\xff\xff')
        expect_failure('proc-read-byte-cap-before-decoding',lambda:q._proc_read(path,1),'proc record byte cap')
    def read_missing(path,cap):
        if path.name=='children':raise FileNotFoundError(2,'missing interface')
        return raw(int(path.parent.name))
    with patch.object(q,'_PROC_STAT_CHILD_ADAPTER',None),patch.object(q,'_proc_read',read_missing),patch.object(q,'_proc_pids',lambda:iter([7])):
        control('proc-self-ENOENT-adapter',lambda:check(q._linux_children(pid)==[7] and q._PROC_STAT_CHILD_ADAPTER is True,'self adapter selection'))
    with patch.object(q,'_PROC_STAT_CHILD_ADAPTER',None),patch.object(q,'_proc_read',side_effect=PermissionError(13,'denied')):
        expect_failure('proc-access-denial-no-fallback',lambda:q._linux_children(pid),'denied')
        check(q._PROC_STAT_CHILD_ADAPTER is None,'denial selected fallback')
    with patch.object(q,'_PROC_STAT_CHILD_ADAPTER',False),patch.object(q,'_proc_read',side_effect=FileNotFoundError(2,'child disappeared')):
        expect_failure('proc-child-disappearance-no-route-switch',lambda:q._linux_children(7),'child disappeared')
        check(q._PROC_STAT_CHILD_ADAPTER is False,'child race selected alternate interface')
    def vanished(n,deadline=None):
        if n==7:raise FileNotFoundError(2,'disappeared')
        return dict(ppid=pid,start=123,state='S')
    with patch.object(q,'_PROC_STAT_CHILD_ADAPTER',True),patch.object(q,'_proc_pids',lambda:iter([7,8])),patch.object(q,'_linux_stat',vanished):
        control('proc-normal-disappearance-race',lambda:check(q._linux_children(pid)==[8],'disappearing record'))
        with patch.object(q,'_PROC_ENTRY_CAP',1):expect_failure('proc-entry-cap',lambda:q._linux_children(pid),'inventory cap')
    with patch.object(q,'_PROC_STAT_CHILD_ADAPTER',True),patch.object(q,'_proc_pids',lambda:iter([7])),patch.object(q,'_proc_read',side_effect=PermissionError(13,'stat denied')):
        expect_failure('proc-stat-denial-fails',lambda:q._linux_children(pid),'stat denied')
    with patch.object(q,'_PROC_STAT_CHILD_ADAPTER',True),patch.object(q,'_PROC_SCAN_SECONDS',0),patch.object(q,'_proc_pids',lambda:iter([7])):
        expect_failure('proc-wall-time-cap',lambda:q._linux_children(pid),'deadline')
    for exited in (False,True):
        tree=object.__new__(q._LinuxTree);tree.known={}
        with patch.object(q,'_linux_stat',side_effect=[dict(ppid=pid,start=123,state='S'),FileNotFoundError(2,'gone')]),patch.object(os,'pidfd_open',return_value=999),patch.object(os,'close'),patch.object(q,'_pidfd_exited',return_value=exited):
            if exited:control('proc-disappearance-after-pidfd-exit',lambda:tree.observe(7,pid))
            else:expect_failure('proc-live-pidfd-missing-record',lambda:tree.observe(7,pid),'live pidfd lost identity record')
    for label,after in [('start',dict(ppid=pid,start=124,state='S')),('link',dict(ppid=pid+1,start=123,state='S'))]:
        tree=object.__new__(q._LinuxTree);tree.known={}
        with patch.object(q,'_linux_stat',side_effect=[dict(ppid=pid,start=123,state='S'),after]),patch.object(os,'pidfd_open',return_value=999),patch.object(os,'close') as close:
            expect_failure('proc-pidfd-'+label+'-mismatch',lambda:tree.observe(7,pid),'pidfd identity/ancestry mismatch')
            check(not tree.known and close.call_args.args==(999,),'uncertain pidfd was admitted')


def lifecycle_controls(root):
    """Real tiny process trees through Recorder and the process-driver adapter."""
    import test_mcp_directory_search as driver
    root.mkdir();ident=identity()
    backend=q._WindowsTree if os.name=='nt' else q._LinuxTree
    def run(kind,label,code,timeout=1,check_after=None):
        directory=root/(kind+'-'+label)
        if kind=='recorder':
            recorder=q.Recorder(directory,ident,['tiny'],dict(os.environ),root,stream_cap=512)
            value=recorder.run('tiny',[sys.executable,'-c',code],timeout,check=check_after)
            return value,directory/'stages/tiny/stdout.bin'
        ev=driver.Evidence(directory)
        with patch.object(driver,'STREAM_CAP',512):
            child=driver.OwnedProcess(ev,[sys.executable,'-c',code],root,dict(os.environ),timeout=timeout)
            child.wait()
        return child.record,child.stdout_path
    for kind in ('recorder','driver'):
        control(kind+'-owned-ordinary-success',lambda kind=kind:run(kind,'valid','print("valid")'))
        for label,redirect,detached in [('inherited-pipe',False,False),('silent-redirected',True,False),('detached-writer',False,True)]:
            pidfile=root/(kind+'-'+label+'.pid')
            child='import time;time.sleep(.5);print("late descendant",flush=True)'
            options=',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL' if redirect else ''
            if detached:options+=',creationflags=subprocess.CREATE_NEW_PROCESS_GROUP' if os.name=='nt' else ',start_new_session=True'
            code='import subprocess,sys;from pathlib import Path;p=subprocess.Popen([sys.executable,"-c",'+repr(child)+']'+options+');Path('+repr(str(pidfile))+').write_text(str(p.pid));print("leader",flush=True)'
            expect_failure(kind+'-'+label,lambda kind=kind,label=label,code=code:run(kind,label,code,.3))
            stdout=root/(kind+'-'+label)/('stages/tiny/stdout.bin' if kind=='recorder' else 'raw/0002-stdout.bin')
            before=q.descriptor(stdout);time.sleep(.55)
            check(q.descriptor(stdout)==before,kind+' descendant changed finalized output')
            RESULTS.append(dict(name=kind+'-'+label+'-stable-hash',passed=True))
        active=backend.active;hidden=[]
        def late_active(tree):
            value=active(tree)
            owner=q._ACTIVE_OWNER
            if value and tree.proc is not None and tree.proc.poll() is not None and not hidden and owner is not None and not any(t.is_alive() for t in owner.readers):
                hidden.append(True);return []
            return value
        late_code='import subprocess,sys;subprocess.Popen([sys.executable,"-c","import time;time.sleep(.5)"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)'
        with patch.object(backend,'active',late_active):
            expect_failure(kind+'-late-finalization-descendant',lambda kind=kind:run(kind,'late-finalization',late_code,.3),'lingering-descendant')
        check(hidden,'late finalization control did not reach terminal boundary')
        expect_failure(kind+'-owned-overflow',lambda kind=kind:run(kind,'overflow','print("x"*1024)'))
        original=q.OwnedChild._drain;finished=[]
        def slow_drain(owner,pipe,path):
            original(owner,pipe,path);finished.append(str(path));time.sleep(.45)
        with patch.object(q.OwnedChild,'_drain',slow_drain):
            expect_failure(kind+'-deadline-through-drain',lambda kind=kind:run(kind,'drain','print("EOF")',.2),'timeout')
        check(finished,'pipe drain control must reach actual EOF')
        for when in ('before','after'):
            attach=backend.attach
            def broken_attach(tree,proc,when=when):
                if when=='after':attach(tree,proc)
                raise ValueError('injected ownership '+when)
            with patch.object(backend,'attach',broken_attach):
                expect_failure(kind+'-ownership-api-'+when,lambda kind=kind,when=when:run(kind,'api-'+when,'import time;time.sleep(1)'), 'injected ownership '+when)
        terminate=backend.terminate;calls=[]
        def broken_terminate(tree):
            terminate(tree)
            if not calls:calls.append(True);raise ValueError('injected cleanup API failure')
        with patch.object(backend,'terminate',broken_terminate):
            expect_failure(kind+'-cleanup-failure-remains-failed',lambda kind=kind:run(kind,'cleanup','import time;time.sleep(1)',.05))
        check(calls,'cleanup failure control reached real termination')
        if kind=='recorder':
            expect_failure('recorder-slow-finalizer',lambda:run(kind,'slow-finalizer','pass',.2,lambda:time.sleep(.3)), 'timeout during stage finalization')
        else:
            original_file=driver.Evidence.file;delayed=[]
            def slow_file(ev,path):
                value=original_file(ev,path)
                if not delayed:delayed.append(True);time.sleep(.3)
                return value
            with patch.object(driver.Evidence,'file',slow_file):
                expect_failure('driver-slow-finalizer',lambda:run(kind,'slow-finalizer','pass',.2),'deadline')
    # Unmanaged siblings make startup reject; never signal that sentinel.
    sentinel=subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        if os.name!='nt':
            for kind in ('recorder','driver'):
                expect_failure(kind+'-unrelated-sentinel-rejected',lambda kind=kind:run(kind,'sentinel','pass'),'unmanaged pre-existing child')
                check(sentinel.poll() is None,'unrelated sentinel was terminated')
        else:
            for kind in ('recorder','driver'):
                run(kind,'unrelated-sentinel','pass')
                check(sentinel.poll() is None,'private Windows job affected unrelated sentinel')
                RESULTS.append(dict(name=kind+'-unrelated-sentinel-survives-private-job',passed=True))
    finally:sentinel.terminate();sentinel.wait(timeout=2)
    if os.name!='nt':
        previous=q.signal.getsignal(q.signal.SIGCHLD)
        q.signal.signal(q.signal.SIGCHLD,q.signal.SIG_IGN)
        try:
            for kind in ('recorder','driver'):
                expect_failure(kind+'-incompatible-reaper-rejected',lambda kind=kind:run(kind,'SIGCHLD','pass'),'incompatible SIGCHLD')
        finally:q.signal.signal(q.signal.SIGCHLD,previous)
    # One active owner blocks both nested helper creation and unmanaged Popen.
    ev=driver.Evidence(root/'intentional-stop')
    server=driver.OwnedProcess(ev,[sys.executable,'-c','import time;print("ready",flush=True);time.sleep(10)'],root,dict(os.environ),timeout=2)
    try:
        expect_failure('concurrent-owner-rejected',lambda:run('recorder','concurrent','pass'),'concurrent owned process rejected')
        expect_failure('unmanaged-launch-rejected',lambda:subprocess.Popen([sys.executable,'-c','pass']),'unmanaged process launch')
        expect_failure('unmanaged-system-launch-rejected',lambda:os.system('exit 0'),'unmanaged process launch')
        server.stop('server_stopped_after_checks')
        check(server.record['ownership']['classification']=='stopped' and server.record['stable'],'intentional server stop failed')
        RESULTS.append(dict(name='driver-intentional-stop',passed=True))
    finally:
        if not server.closed:server.stop('cleanup')
    # A finite Recorder command can itself exercise a serial intentional fixture stop.
    code='import sys,os,subprocess;from pathlib import Path;sys.path.insert(0,'+repr(str(Path(q.__file__).parent))+');from run_n49d_qualification import OwnedChild;p=Path('+repr(str(root))+');c=OwnedChild([sys.executable,"-c","import time;time.sleep(10)"],p,dict(os.environ),subprocess.DEVNULL,p/"inner-out",p/"inner-err",2,512);r=c.stop();raise SystemExit(0 if r["classification"]=="stopped" and r["stable"] else 9)'
    control('recorder-intentional-stop-in-owned-command',lambda:run('recorder','intentional',code,3))


def tiny_bundle(root):
    """Synthetic complete approved-source/command fixture, not native execution."""
    root.mkdir();paths=sorted(guard.ALLOW);nodes={};rows={};inventory=b''
    for path in paths:
        data=('synthetic source fixture only: '+path+'\n').encode('utf-8');oid=guard.blob(data)
        dest=root/'source/changed'/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        rows[path]=dict(mode='100644',blob=oid,sha256=hashlib.sha256(data).hexdigest())
        inventory+=b'100644 blob '+oid.encode()+b'\t'+path.encode()+b'\0'
        node=nodes;parts=path.split('/')
        for part in parts[:-1]:node=node.setdefault(part,{})
        node[parts[-1]]=oid
    def tree_hash(node):
        body=b''
        for name,value in sorted(node.items(),key=lambda row:row[0]+('/' if isinstance(row[1],dict) else '')):
            directory=isinstance(value,dict)
            body+=(b'40000' if directory else b'100644')+b' '+name.encode()+b'\0'+bytes.fromhex(tree_hash(value) if directory else value)
        return hashlib.sha1(b'tree '+str(len(body)).encode()+b'\0'+body).hexdigest()
    tree=tree_hash(nodes);ident=identity(tree)
    source=dict(passed=True,commit=ident['commit'],tree=tree,base=guard.BASE,base_tree=guard.BASE_TREE,precommit=False,
                inventory_sha256=hashlib.sha256(inventory).hexdigest(),changed=paths,changed_files=rows,dependency_sha256={})
    q.dump(root/'reports/source-before.json',source);q.dump(root/'reports/source-after.json',source)
    (root/'source/tree-inventory.bin').write_bytes(inventory);q.dump(root/'source/dependencies.json',{})
    (root/'binaries').mkdir();binary=root/'binaries/qbrain';binary.write_bytes(b'fixture binary only')
    bd=q.descriptor(binary);required=q.required_stages(ident['job_key'])
    locations=dict(source='/fixture/source',build='/fixture/build',output='/fixture/evidence',python='/fixture/python')
    specs=q.stage_contract(ident,locations);prod='/fixture/build/qbrain'
    for mode in ('normal','optimized'):
        mcp=root/'reports'/('mcp_directory_search-'+mode);(mcp/'raw').mkdir(parents=True)
        (mcp/'raw/fixture.bin').write_bytes(b'fixture')
        blob=dict(path='raw/fixture.bin',bytes=7,sha256=hashlib.sha256(b'fixture').hexdigest())
        owned=dict(classification='passed',cleanup_ok=True,stable=True,readers_done=True,exit=0,stdout=dict(size=7,sha256=blob['sha256']),stderr=dict(size=7,sha256=blob['sha256']))
        q.dump(mcp/'RESULT.json',dict(
            schema='qbrain-n49d-mcp-directory-process-v1',passed=True,status='passed',python_optimized=mode=='optimized',
            binary_sha256=bd['sha256'],stdio=dict(status='passed',profiles=['full','memory']),
            http=dict(required=False,status='not_applicable'),provider_http=dict(required=False,status='not_applicable'),
            command_count=1,commands=[dict(argv=[prod,'fixture-only'],status='completed',exit=0,stable=True,ownership=owned,stdin=blob,stdout=blob,stderr=blob)],exchange_count=0,exchanges=[]))
        q.dump(root/'reports'/('directory_search-'+mode)/'RESULT.json',dict(passed=True,checks=[dict(passed=True)],check_count=1,commands=[dict(fixture=True)],command_count=1))
        q.dump(root/'reports'/('context_process-'+mode+'.json'),dict(format_version=1,checks=1,provider_calls=0))
        q.dump(root/'reports'/('named_arguments-'+mode+'.json'),dict(passed=1,failed=0,checks=[dict(passed=True)],commands=[dict(fixture=True)],command_count=1,binary_sha256=bd['sha256']))
    (root/'reports/ctest.xml').write_text('<testsuite>'+''.join('<testcase name="'+name+'"/>' for name in q.TESTS)+'</testsuite>')
    for name in required:
        spec=specs[name];folder=root/'stages'/name;folder.mkdir(parents=True)
        stdout=b'fixture-only\n'
        if name=='ctest-inventory':stdout=json.dumps(dict(tests=[dict(name=n) for n in q.TESTS])).encode()
        elif name=='ctest-completeness':stdout=json.dumps(list(q.TESTS)).encode()
        elif name.startswith('selftest-'):stdout=json.dumps(dict(passed=True,python_optimized=name.endswith('optimized'),controls=[dict(name='fixture',passed=True)])).encode()
        (folder/'stdout.bin').write_bytes(stdout);(folder/'stderr.bin').write_bytes(b'')
        q.dump(folder/'result.json',dict(name=name,identity=ident,argv=spec['argv'],timeout_seconds=spec['timeout_seconds'],cwd=locations['source'],exit=0,classification='passed',ownership=dict(classification='passed',cleanup_ok=True,stable=True,readers_done=True,exit=0,stdout=q.descriptor(folder/'stdout.bin'),stderr=q.descriptor(folder/'stderr.bin')),
            stdout=q.descriptor(folder/'stdout.bin'),stderr=q.descriptor(folder/'stderr.bin'),requested_reports=spec['reports'],reports={p:q.descriptor(root/p) for p in spec['reports']},
            binaries_before={p:bd for p in spec['binaries_before']},binaries_after={p:bd for p in spec['binaries_after']}))
    binding=q.descriptor(root/'reports/source-before.json')
    q.dump(root/'qualification.json',dict(passed=True,identity=ident,required=required,stages=required,locations=locations,
        source_before=binding,source_after=binding,binaries={p:bd for spec in specs.values() for p in spec['binaries_after']},
        retained_binaries={prod:dict(path='binaries/qbrain',**bd)}))
    return ident


def make_archive(evidence, archive, ident):
    rows=[]
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(evidence.rglob('*')):
            if not p.is_file():continue
            name=p.relative_to(evidence).as_posix();info=zipfile.ZipInfo(name);info.create_system=3
            info.external_attr=(stat.S_IFREG|0o644)<<16;info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,p.read_bytes());rows.append(dict(path=name,mode=stat.S_IFREG|0o644,**q.descriptor(p)))
    desc=q.descriptor(archive)
    manifest=dict(schema='qbrain-n49c-evidence-parts-v1',identity=ident,files=rows,
                  uncompressed_bytes=sum(r['size'] for r in rows),archive=desc,
                  parts=[dict(index=0,file='evidence.part',**desc)])
    return json.dumps(manifest,sort_keys=True).encode()


def wrap(archive, raw, outer, extra=None, omit=None):
    with zipfile.ZipFile(outer,'w',zipfile.ZIP_STORED) as z:
        for name,data in [('manifest.json',raw),('evidence.part',archive.read_bytes())]:
            if name!=omit:z.writestr(name,data)
        if extra:z.writestr(extra,b'x')


def package_consumer_controls(root):
    evidence=root/'evidence';ident=tiny_bundle(evidence)
    archive=root/'tiny.zip';raw=make_archive(evidence,archive,ident);outer=root/'outer.zip';wrap(archive,raw,outer)
    data={p.relative_to(evidence).as_posix():p.read_bytes() for p in evidence.rglob('*') if p.is_file()}
    control('full-fixed-command-report-contract-valid',lambda:q.validate_recordings(data.__getitem__,ident,files=data))
    for name,report_path in [('ctest-run','reports/ctest.xml'),('directory_search-normal','reports/directory_search-normal/RESULT.json'),
                             ('context_process-normal','reports/context_process-normal.json'),('named_arguments-normal','reports/named_arguments-normal.json')]:
        omitted=dict(data);del omitted[report_path];path='stages/'+name+'/result.json';stage=json.loads(omitted[path]);stage['reports']={};stage['requested_reports']=[];omitted[path]=json.dumps(stage).encode()
        expect_failure('full-contract-omitted-'+name,lambda omitted=omitted:q.validate_recordings(omitted.__getitem__,ident,files=omitted),'fixed required report inventory mismatch')
    wrong=dict(data);path='stages/selftest-normal/result.json';stage=json.loads(wrong[path]);stage['argv']=['fixture-only'];wrong[path]=json.dumps(stage).encode()
    expect_failure('full-contract-changed-command',lambda:q.validate_recordings(wrong.__getitem__,ident,files=wrong),'fixed stage command mismatch')
    source_path='.ci/run_n49d_qualification.py';source_leaf='source/changed/'+source_path
    def source_packet(change):
        packet=dict(data);binding=json.loads(packet['reports/source-before.json']);change(binding,packet)
        binding_raw=json.dumps(binding,sort_keys=True).encode();desc=dict(size=len(binding_raw),sha256=hashlib.sha256(binding_raw).hexdigest())
        # Rebind every recorded report descriptor, so negatives reach source semantics.
        for label in ('source-before','source-after'):
            report='reports/'+label+'.json';packet[report]=binding_raw
            stage_path='stages/'+label+'/result.json';stage=json.loads(packet[stage_path]);stage['reports'][report]=desc
            packet[stage_path]=json.dumps(stage).encode()
        result=json.loads(packet['qualification.json']);result['source_before']=desc;result['source_after']=desc
        packet['qualification.json']=json.dumps(result).encode()
        return packet
    omitted_source=source_packet(lambda binding,packet:(binding['changed_files'].pop(source_path),packet.pop(source_leaf)))
    expect_failure('full-source-omitted-leaf-and-map-rehashed',lambda:q.validate_recordings(omitted_source.__getitem__,ident,files=omitted_source),'fixed changed source map mismatch')
    cases=[
        ('omitted-list-map-leaf',lambda b,p:(b['changed'].remove(source_path),b['changed_files'].pop(source_path),p.pop(source_leaf)),'list'),
        ('mismatched-list',lambda b,p:b['changed'].remove(source_path),'list'),
        ('mismatched-map',lambda b,p:b['changed_files'].pop(source_path),'map'),
        ('duplicate-list',lambda b,p:b['changed'].append(source_path),'list'),
        ('unsorted-list',lambda b,p:b['changed'].reverse(),'list'),
        ('unexpected-list',lambda b,p:b['changed'].append('unexpected.txt'),'list'),
        ('unexpected-map',lambda b,p:b['changed_files'].update({'unexpected.txt':b['changed_files'][source_path]}),'map'),
        ('missing-leaf',lambda b,p:p.pop(source_leaf),'leaf inventory'),
        ('unexpected-leaf',lambda b,p:p.update({'source/changed/unexpected.txt':b'unexpected'}),'leaf inventory'),
        ('altered-bytes',lambda b,p:p.update({source_leaf:b'changed source bytes'}),'bytes'),
        ('altered-mode',lambda b,p:b['changed_files'][source_path].update(mode='100755'),'bytes'),
        ('altered-blob',lambda b,p:b['changed_files'][source_path].update(blob='0'*40),'bytes'),
        ('altered-hash',lambda b,p:b['changed_files'][source_path].update(sha256='0'*64),'bytes'),
        ('altered-bytes-and-map',lambda b,p:(p.update({source_leaf:b'changed source bytes'}),b['changed_files'][source_path].update(blob=guard.blob(b'changed source bytes'),sha256=hashlib.sha256(b'changed source bytes').hexdigest())),'bytes')]
    for label,change,boundary in cases:
        packet=source_packet(change)
        expect_failure('full-source-'+label+'-rehashed',lambda packet=packet:q.validate_recordings(packet.__getitem__,ident,files=packet),'changed source '+boundary)
    expect_failure('full-source-duplicate-leaf-inventory',lambda:q.validate_recordings(data.__getitem__,ident,files=list(data)+[source_leaf]),'fixed changed source leaf inventory mismatch')
    expect_failure('full-source-absent-leaf-inventory',lambda:q.validate_recordings(data.__getitem__,ident),'complete evidence inventory required')
    calls=[]
    def tiny_packager(src,staging,expected):
        calls.append(str(staging));staging=Path(staging);staging.mkdir();zip_path=staging/'tiny.zip'
        manifest=make_archive(Path(src),zip_path,expected);part=staging/'parts/00';part.mkdir(parents=True)
        (part/'evidence.part').write_bytes(zip_path.read_bytes());(part/'manifest.json').write_bytes(manifest)
        return dict(passed=True,identity=expected,parts_root=str(staging/'parts'),part_count=1,
            archive_size=zip_path.stat().st_size,archive_sha256=q.digest(zip_path),manifest_bytes=len(manifest),manifest_sha256=hashlib.sha256(manifest).hexdigest())
    control('actual-package-wrapper-valid-injected-generic',lambda:q.package(evidence,root/'package-valid',ident,_generic_packager=tiny_packager))
    check(len(calls)==1,'actual package wrapper must invoke generic seam once')
    def rejected_packager(*args):raise ValueError('injected generic package failure')
    expect_failure('actual-package-wrapper-generic-failure',lambda:q.package(evidence,root/'package-generic-failure',ident,_generic_packager=rejected_packager),'injected generic package failure')
    expect_failure('actual-package-wrapper-post-compressed-cap',lambda:q.package(evidence,root/'package-compressed-cap',ident,dict(q.LIMITS,compressed=1),_generic_packager=tiny_packager),'N49D compressed cap')
    def wrong_result(src,staging,expected):
        result=tiny_packager(src,staging,expected);result['manifest_sha256']='0'*64;return result
    expect_failure('actual-package-wrapper-result-binding',lambda:q.package(evidence,root/'package-wrong-result',ident,_generic_packager=wrong_result),'generic package result digest mismatch')
    before_calls=len(calls)
    expect_failure('actual-package-wrapper-pre-raw-cap',lambda:q.package(evidence,root/'package-raw-cap',ident,dict(q.LIMITS,raw=1),_generic_packager=tiny_packager),'raw/member cap exceeded')
    check(len(calls)==before_calls,'raw cap must reject before generic invocation')

    control('package-preflight-valid',lambda:q.evidence_inventory(evidence))
    control('package-postflight-valid',lambda:q.validate_manifest(raw,ident))
    control('unchanged-archive-validator-valid',lambda:q.generic_archive()['verify_evidence_archive'](archive,json.loads(raw)))
    review=root/'review';review.mkdir();outer.rename(review/outer.name);outer=review/outer.name
    limits=dict(q.LIMITS,reserve=0,compressed=128*1024,text=256*1024,staging=1024*1024,outer=256*1024)
    sha=hashlib.sha256(raw).hexdigest()
    control('consumer-valid',lambda:q.consume(outer,review,ident,sha,q.digest(outer),limits))
    result=json.loads(data['qualification.json']);manifest=json.loads(raw);selection=q.review_selection(result,manifest['files'])
    selected={r['path'] for r in selection}
    check('reports/source-after.json' not in selected and 'stages/source-before/stdout.bin' not in selected and
          'reports/mcp_directory_search-normal/RESULT.json' in selected and not any(p.startswith('binaries/') for p in selected) and
          {p for p in selected if p.startswith('source/changed/')}=={'source/changed/'+p for p in guard.ALLOW}, 'explicit materialized review subset')
    RESULTS.append(dict(name='explicit-review-selection-valid',passed=True))
    expect_failure('review-selection-missing-mandatory',lambda:q.review_selection(result,[r for r in manifest['files'] if r['path']!='source/dependencies.json']), 'required review selection missing')
    source_row=next(r for r in manifest['files'] if r['path']==source_leaf)
    expect_failure('review-selection-missing-source',lambda:q.review_selection(result,[r for r in manifest['files'] if r['path']!=source_leaf]),'fixed changed source leaf inventory mismatch')
    expect_failure('review-selection-duplicate-source',lambda:q.review_selection(result,manifest['files']+[source_row]),'fixed changed source leaf inventory mismatch')
    expect_failure('review-selection-unexpected-source',lambda:q.review_selection(result,manifest['files']+[dict(source_row,path='source/changed/unexpected.txt')]),'fixed changed source leaf inventory mismatch')
    omitted_root=root/'source-omission-evidence';omitted_root.mkdir()
    for name,value in omitted_source.items():
        dest=omitted_root/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(value)
    expect_failure('actual-package-omitted-source-and-map',lambda:q.package(omitted_root,root/'source-omission-package',ident,_generic_packager=tiny_packager),'fixed changed source map mismatch')
    omitted_archive=root/'source-omission.zip';omitted_manifest=make_archive(omitted_root,omitted_archive,ident)
    omitted_review=root/'source-omission-review';omitted_review.mkdir();omitted_outer=omitted_review/'download.zip';wrap(omitted_archive,omitted_manifest,omitted_outer)
    expect_failure('consumer-omitted-source-and-map-rehashed',lambda:q.consume(omitted_outer,omitted_review,ident,hashlib.sha256(omitted_manifest).hexdigest(),q.digest(omitted_outer),limits),'fixed changed source map mismatch')
    cap_root=root/'selection-cap';cap_root.mkdir();cap_outer=cap_root/'download.zip';cap_outer.write_bytes(outer.read_bytes())
    expect_failure('review-selection-cumulative-size-cap',lambda:q.consume(cap_outer,cap_root,ident,sha,q.digest(cap_outer),dict(limits,text=sum(r['size'] for r in selection)-1)), 'aggregate retained-text cap')
    raw_path=evidence/'reports/mcp_directory_search-normal/raw/fixture.bin';old_raw=raw_path.read_bytes();raw_path.write_bytes(b'changed')
    changed_archive=root/'unselected-raw.zip';changed_manifest=make_archive(evidence,changed_archive,ident);changed_outer=review/'unselected-raw.zip';wrap(changed_archive,changed_manifest,changed_outer)
    expect_failure('unselected-raw-still-semantically-checked',lambda:q.consume(changed_outer,review,ident,hashlib.sha256(changed_manifest).hexdigest(),q.digest(changed_outer),limits), 'MCP raw evidence mismatch')
    raw_path.write_bytes(old_raw)

    expect_failure('out-of-root-unaccounted-download',lambda:q.consume(outer,root/'unaccounted',ident,sha,q.digest(outer),limits),'download must reside in aggregate review staging')
    expect_failure('cumulative-retained-text-cap',lambda:q.consume(outer,review,ident,sha,q.digest(outer),
        dict(limits,text=q.review_text_bytes(review)-1)),'aggregate retained-text cap')
    expect_failure('cumulative-staging-cap',lambda:q.consume(outer,review,ident,sha,q.digest(outer),
        dict(limits,staging=q.staging_size(review)+limits['compressed']+limits['text']-q.review_text_bytes(review)-1)),'consumer staging cap')

    for name,key,value in [('manifest-cap','manifest',len(raw)-1),('member-count-cap','members',1),
                           ('raw-size-cap','raw',1),('compressed-size-cap','compressed',1)]:
        cap=dict(q.LIMITS);cap[key]=value
        expect_failure(name,lambda cap=cap:q.validate_manifest(raw,ident,cap))
    for name,key in [('package-input-raw-cap','raw'),('package-input-member-cap','members')]:
        cap=dict(q.LIMITS);cap[key]=1
        expect_failure(name,lambda cap=cap:q.evidence_inventory(evidence,cap))
    expect_failure('consumer-staging-cap',lambda:q.consume(outer,review,ident,sha,q.digest(outer),dict(limits,staging=1)),'consumer staging cap')
    for name,kwargs in [('missing-outer-member',dict(omit='evidence.part')),('extra-outer-member',dict(extra='extra'))]:
        bad=review/(name+'.zip');wrap(archive,raw,bad,**kwargs)
        expect_failure(name,lambda bad=bad:q.consume(bad,review,ident,sha,q.digest(bad),limits),'missing/extra outer member')
    expect_failure('wrong-manifest-hash',lambda:q.consume(outer,review,ident,'0'*64,q.digest(outer),limits),'independent manifest digest mismatch')
    expect_failure('wrong-artifact-hash',lambda:q.consume(outer,review,ident,sha,'0'*64,limits),'independent GitHub artifact digest mismatch')
    broken=root/'broken.zip';broken.write_bytes(bytes([archive.read_bytes()[0]^1])+archive.read_bytes()[1:]);bad=review/'wrong-part.zip';wrap(broken,raw,bad)
    expect_failure('wrong-part-hash',lambda:q.consume(bad,review,ident,sha,q.digest(bad),limits),'wrong part digest')
    for name,key,value in [('wrong-job','job_key','windows-cmake'),('wrong-run-attempt','run_attempt','3'),('wrong-candidate','commit','5'*40)]:
        badident=dict(ident);badident[key]=value
        if key=='job_key':badident['job_label']=value
        expect_failure(name,lambda badident=badident,name=name:q.consume(outer,review,badident,sha,q.digest(outer),limits),'candidate/job/run identity mismatch')
    # Mutated bytes remain rejected even when the outer and leaf transport hashes are regenerated.
    (evidence/'binaries/qbrain').write_bytes(b'mutated binary')
    altered=root/'altered.zip';altered_raw=make_archive(evidence,altered,ident);altered_outer=review/'altered-outer.zip';wrap(altered,altered_raw,altered_outer)
    expect_failure('consumer-mutated-binary',lambda:q.consume(altered_outer,review,ident,
        hashlib.sha256(altered_raw).hexdigest(),q.digest(altered_outer),limits),'retained binary bytes mutated')
    # Verify the public consumer CLI returns a failing process status as well.
    ident_file=root/'identity.json';q.dump(ident_file,ident)
    process=subprocess.run([sys.executable,str(Path(q.__file__)),'consume','--outer',str(outer),'--review-root',str(review),
        '--identity',str(ident_file),'--manifest-sha256','0'*64,'--artifact-sha256',q.digest(outer)],capture_output=True,timeout=10)
    check(process.returncode!=0,'consumer CLI failure status');RESULTS.append(dict(name='consumer-nonzero-return',passed=True))


def main():
    with tempfile.TemporaryDirectory(prefix='n49d-tiny-controls-') as tmp:
        root=Path(tmp);source_controls();audit_launch_controls();proc_reader_controls();(root/'recorder').mkdir();(root/'package').mkdir();recorder_controls(root/'recorder');package_consumer_controls(root/'package');lifecycle_controls(root/'lifecycle')
    print(json.dumps(dict(passed=True,python_optimized=sys.flags.optimize>0,controls=RESULTS,
        n49d_package_wrapper_executed=True,generic_package_fixture_seam=True,inherited_packager_executed=False,inherited_packager_reason='unchanged 1152 MiB reserve; native CI only'),sort_keys=True))
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print(json.dumps(dict(passed=False,error=str(e),controls=RESULTS)),file=sys.stderr);sys.exit(1)
