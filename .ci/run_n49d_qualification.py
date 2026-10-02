"""Fixed N49D native stages, bounded evidence recording and artifact consumption.

The generic inherited ZIP format is transport only, not historical qualification.
No historical source, phase, fixture or probe qualifier is imported or called.
"""
from __future__ import annotations

import argparse
import ast
import base64
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
import xml.etree.ElementTree as ET

import check_n49d_sources as source_guard

MIB = 1024 * 1024
LIMITS = dict(compressed=20*MIB, manifest=512*1024, raw=160*MIB, members=4096,
              outer=21*MIB-1, staging=110*MIB, text=6*MIB, reserve=150*MIB)
JOBS = ('linux-cmake', 'windows-cmake', 'windows-msvc', 'linux-sanitizers')
TARGETS = ('qbrain_mcp_directory_search_tests', 'qbrain_directory_search_tests',
           'qbrain_memory_tests', 'qbrain_context_tests', 'qbrain_http_tests',
           'qbrain_retrieval_tests', 'qbrain_embedding_tests', 'qbrain_embedding_queue_tests',
           'qbrain_cjk_tests', 'qbrain_recall_tests', 'qbrain_strict_json_tests', 'qbrain_multiterm_tests')
TESTS = ('qbrain_mcp_directory_search_unit', 'qbrain_directory_search_unit',
         'qbrain_memory_unit', 'qbrain_context_unit', 'qbrain_http_input_unit',
         'qbrain_retrieval_unit', 'qbrain_embedding_unit', 'qbrain_embedding_queue_unit',
         'qbrain_cjk_unit', 'qbrain_recall_unit', 'qbrain_strict_json_unit', 'qbrain_multiterm_unit')
DRIVERS = ('mcp_directory_search', 'directory_search', 'context_process', 'hooks', 'memory_cycle', 'named_arguments')
BLOCKED = re.compile(r'^(QBRAIN|PG|CURSOR|OPENAI|ANTHROPIC|GH_TOKEN|GITHUB_TOKEN|AWS_|AZURE_|GOOGLE_|GCP_|ZHIPU|GEMINI|COHERE|MISTRAL|DEEPSEEK|HF_|HUGGINGFACE|OPENROUTER|GIT_CONFIG_)|(?:^|_)(?:API_KEY|TOKEN|SECRET|PASSWORD|PASSWD|DSN|DATABASE_URL)(?:_|$)', re.I)
ROOT = Path(__file__).resolve().parents[1]
need = source_guard.need


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while data := f.read(MIB):
            h.update(data)
    return h.hexdigest()


def dump(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def descriptor(path):
    p = Path(path)
    need(p.is_file() and not p.is_symlink(), 'required regular file missing')
    return dict(size=p.stat().st_size, sha256=digest(p))


def same_identity(value, expected):
    need(value == expected and set(value) == {'commit','tree','run_id','run_attempt','job_key','job_label'},
         'candidate/job/run identity mismatch')
    need(all(isinstance(v,str) and v for v in value.values()), 'identity strings required')
    need(all(re.fullmatch('[0-9a-f]{40}', value[k]) for k in ('commit','tree')), 'invalid candidate identity')
    need(value['run_id'].isdigit() and value['run_attempt'].isdigit(), 'invalid run identity')
    need(value['job_key'] in JOBS and value['job_label'] == value['job_key'], 'unknown job')


def generic_archive(root=ROOT):
    """AST-select unchanged generic primitives and their ORIGINAL constants."""
    path = Path(root) / '.ci/check_n49c_sources.py'
    raw = source_guard.checkout_bytes(path.read_bytes(), '45a9c078a261270f595642f2d4c0092ad3c74243', os.name == 'nt')
    names = {'need','hash_file','safe_member','evidence_identity','bounded_manifest',
             'ManifestBudgetExceeded','encode_manifest','BoundedArchive',
             'verify_evidence_archive','verify_evidence_parts','package_evidence'}
    constants = {'BLOCK','PART_BYTES','MAX_PARTS','MAX_ARCHIVE','MAX_RAW','MAX_MANIFEST','MIN_FREE','IDENTITY_KEYS'}
    nodes = []
    for node in ast.parse(raw.decode('utf-8')).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            nodes.append(node)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in constants:
            nodes.append(node)
    need({n.name for n in nodes if isinstance(n,(ast.FunctionDef,ast.ClassDef))} == names, 'primitive inventory mismatch')
    ns = dict(Path=Path,ROOT=Path(root),hashlib=hashlib,os=os,re=re,stat=stat,json=json,
              shutil=shutil,tempfile=tempfile,zipfile=zipfile)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
    need(ns['MIN_FREE'] == 1152*MIB and ns['MAX_ARCHIVE'] == 320*MIB, 'inherited limits must remain unchanged')
    return ns


def required_stages(job):
    need(job in JOBS, 'unknown job')
    result = ['source-before','selftest-normal','selftest-optimized']
    if job == 'windows-msvc':
        result += ['direct-production','direct-tests','canonical-groups']
    else:
        result += ['configure','build']
        if job == 'linux-sanitizers':
            result += ['sanitizer-flags','sanitize-mcp','sanitize-directory']
        else:
            result += ['ctest-inventory','ctest-run','ctest-completeness']
            if job == 'windows-cmake':
                result += ['canonical-build','canonical-run','canonical-groups']
    if job != 'linux-sanitizers':
        for mode in ('normal','optimized'):
            result += [f'{driver}-{mode}' for driver in DRIVERS]
            if job == 'windows-cmake':
                result += [f'winhttp-{mode}']
    return result + ['source-after']


def stage_contract(identity, locations):
    """Exact production argv, report inventory and deadlines; no shell fragments."""
    import ntpath, posixpath
    job=identity['job_key']; windows=job.startswith('windows'); path=ntpath if windows else posixpath
    need(set(locations)=={'source','build','output','python'}, 'fixed location inventory')
    need(all(isinstance(v,str) and path.isabs(v) for v in locations.values()), 'absolute stage locations required')
    source,build,output,python=(locations[k] for k in ('source','build','output','python'))
    need(re.fullmatch(r'python(?:[0-9]+(?:\.[0-9]+)*)?(?:\.exe)?',path.basename(python),re.I), 'Python executable identity')
    need(len({path.normcase(v) for v in (source,build,output)})==3, 'stage locations overlap')
    join=path.join; ci=lambda p:join(source,'.ci',p); report=lambda p:join(output,'reports',p)
    exe=lambda name:join(build,'Debug',name+'.exe') if windows else join(build,name)
    runner=ci('run_n49d_qualification.py'); specs={}
    def add(name,argv,timeout=600,reports=()):
        specs[name]=dict(argv=list(argv),timeout_seconds=timeout,reports=list(reports))
    for name in ('source-before','source-after'):
        add(name,[python,ci('check_n49d_sources.py'),'--source',source,'--commit',identity['commit'],'--tree',identity['tree'],'--report',report(name+'.json')],120,['reports/'+name+'.json'])
    for mode in ('normal','optimized'):
        add('selftest-'+mode,[python,*(['-O'] if mode=='optimized' else []),ci('test_n49d_source_contract.py')],120)
    if job=='windows-msvc':
        production=join(source,'build','cl','qbrain.exe')
        add('direct-production',['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File','scripts/build-cl.ps1'],1800)
        add('direct-tests',['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File','scripts/build-tests-cl.ps1','-SkipProductionBuild'],1800)
        native_log=join(output,'stages','direct-tests','stdout.bin')
    else:
        configure=['cmake','-S',source,'-B',build,'-DQBRAIN_WITH_PG=OFF','-DCMAKE_PROJECT_qbrain_INCLUDE='+ci('mcp_directory_search_targets.cmake'),'-DCMAKE_BUILD_TYPE=Debug']
        targets=['qbrain',*TARGETS];production=exe('qbrain')
        if job=='linux-sanitizers':
            configure+=['-DCMAKE_C_COMPILER=clang','-DCMAKE_CXX_COMPILER=clang++','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
                '-DCMAKE_C_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer','-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer',
                '-DCMAKE_C_FLAGS_DEBUG=-O1 -g0','-DCMAKE_CXX_FLAGS_DEBUG=-O1 -g0','-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined']
            targets=list(TARGETS[:2])
        elif job=='linux-cmake':configure+=['-DCMAKE_CXX_FLAGS_DEBUG=-O0 -g0','-DCMAKE_C_FLAGS_DEBUG=-O0 -g0']
        add('configure',configure,180)
        add('build',['cmake','--build',build,'--config','Debug','--target',*targets,'--parallel','2'],1800)
        if job=='linux-sanitizers':
            add('sanitizer-flags',[python,runner,'verify-sanitizer','--build',build,'--report',report('sanitizer-effective.json')],120,['reports/sanitizer-effective.json'])
            for name,target in zip(('sanitize-mcp','sanitize-directory'),TARGETS[:2]):add(name,[exe(target)])
        else:
            regex='^('+'|'.join(TESTS)+')$';inventory=join(output,'stages','ctest-inventory','stdout.bin')
            add('ctest-inventory',['ctest','--test-dir',build,'-C','Debug','-R',regex,'--show-only=json-v1'],120)
            add('ctest-run',['ctest','--test-dir',build,'-C','Debug','-R',regex,'--output-on-failure','--output-junit',report('ctest.xml')],600,['reports/ctest.xml'])
            add('ctest-completeness',[python,runner,'verify-ctest','--inventory',inventory,'--junit',report('ctest.xml')],120)
            if windows:
                add('canonical-build',['cmake','--build',build,'--config','Debug','--target','qbrain_tests','qbrain_http_probe','--parallel','2'],1800)
                add('canonical-run',[exe('qbrain_tests')]);native_log=join(output,'stages','canonical-run','stdout.bin')
    if windows:add('canonical-groups',[python,runner,'verify-native','--registry',join(source,'tests','test_main.cpp'),'--log',native_log],120)
    if job!='linux-sanitizers':
        for mode in ('normal','optimized'):
            prefix=[python,*(['-O'] if mode=='optimized' else [])]
            for driver in DRIVERS:
                name=driver+'-'+mode;argv=prefix+[ci('test_'+driver+'.py'),'--binary',production];reports=[]
                if driver in ('mcp_directory_search','directory_search'):
                    argv+=['--output',report(name)];reports=['reports/'+name+'/RESULT.json']
                elif driver in ('context_process','named_arguments'):
                    argv+=['--report',report(name+'.json')];reports=['reports/'+name+'.json']
                add(name,argv,reports=reports)
            if job=='windows-cmake':
                name='winhttp-'+mode;add(name,prefix+[ci('test_http_transport.py'),'--probe',exe('qbrain_http_probe'),'--report',report(name+'.json')],reports=['reports/'+name+'.json'])
    selected=[exe(t) for t in (TARGETS[:2] if job=='linux-sanitizers' else ['qbrain',*TARGETS])]
    canonical=join(source,'build','cl','qbrain_tests.exe') if job=='windows-msvc' else exe('qbrain_tests')
    for name,spec in specs.items():
        before=[];after=[]
        if name=='build':after=selected
        elif name=='direct-production':after=[production]
        elif name=='direct-tests':before=[production];after=[production,canonical]
        elif name in ('ctest-inventory','ctest-run','ctest-completeness','sanitizer-flags','sanitize-mcp','sanitize-directory'):before=selected
        elif name=='canonical-build':before=selected;after=selected+[canonical,exe('qbrain_http_probe')]
        elif name in ('canonical-run','canonical-groups'):before=[canonical,production]
        elif any(name==driver+'-'+mode for driver in DRIVERS for mode in ('normal','optimized')):before=[production]
        elif name.startswith('winhttp-'):before=[production,exe('qbrain_http_probe')]
        spec['binaries_before']=sorted(before);spec['binaries_after']=sorted(after or before)
    all_binaries=sorted({p for spec in specs.values() for p in spec['binaries_after']})
    specs['source-after']['binaries_before']=all_binaries;specs['source-after']['binaries_after']=all_binaries
    need(set(specs)==set(required_stages(job)), 'fixed stage contract inventory')
    return specs


_OWNER_LOCK=threading.Lock()
_ACTIVE_OWNER=None
_AUDIT_INSTALLED=False
_LAUNCH_THREAD=None
_LAUNCH_ARGV=None


def _audit_launch(event,args):
    if _ACTIVE_OWNER is None:return
    if event in ('os.system','os.spawn','os.exec','os.startfile','os.startfile/2','pty.spawn'):
        raise ValueError('unmanaged process launch during owned lifetime')
    if event in ('subprocess.Popen','os.fork','os.forkpty','os.posix_spawn'):
        allowed=threading.get_ident()==_LAUNCH_THREAD
        if event=='subprocess.Popen' and os.name=='nt':
            allowed=allowed and isinstance(args[1],str) and args[1]==subprocess.list2cmdline(_LAUNCH_ARGV)
        elif event in ('subprocess.Popen','os.posix_spawn'):
            allowed=allowed and isinstance(args[1],(list,tuple)) and list(args[1])==_LAUNCH_ARGV
        need(allowed,'unmanaged process launch during owned lifetime')


_PROC_STAT_CHILD_ADAPTER=None
_PROC_ENTRY_CAP=16384
_PROC_RECORD_CAP=4096
_PROC_SCAN_SECONDS=.25


def _proc_read(path,cap):
    with path.open('rb') as source:raw=source.read(cap+1)
    need(len(raw)<=cap,'proc record byte cap')
    return raw.decode('utf-8',errors='strict')


def _parse_proc_stat(text,pid):
    need(len(text.encode('utf-8',errors='strict'))<=_PROC_RECORD_CAP,'proc stat record cap')
    left=text.find(' (');right=text.rfind(') ')
    need(left>0 and right>left and text[:left].isdecimal() and int(text[:left])==pid,'proc stat PID/comm mismatch')
    fields=text[right+2:].split()
    need(len(fields)>=20 and len(fields[0])==1,'incomplete proc stat record')
    try:ppid=int(fields[1]);start=int(fields[19])
    except ValueError as error:raise ValueError('invalid proc identity fields') from error
    need(ppid>=0 and start>0,'invalid proc identity values')
    return dict(state=fields[0],ppid=ppid,start=start)


def _proc_deadline():
    outer=getattr(_ACTIVE_OWNER,'scan_deadline',float('inf'))
    return min(outer,time.monotonic()+_PROC_SCAN_SECONDS)


def _linux_stat(pid,deadline=None):
    deadline=_proc_deadline() if deadline is None else deadline
    need(time.monotonic()<deadline,'proc read deadline')
    result=_parse_proc_stat(_proc_read(Path('/proc',str(pid),'stat'),_PROC_RECORD_CAP),pid)
    need(time.monotonic()<deadline,'proc read deadline')
    return result


def _proc_pids():
    return (int(entry.name) for entry in Path('/proc').iterdir() if entry.name.isdecimal())


def _linux_children(pid):
    global _PROC_STAT_CHILD_ADAPTER
    deadline=_proc_deadline()
    if _PROC_STAT_CHILD_ADAPTER is None:
        # Selection is a self-process capability preflight, never a child race
        # or a permission-denial fallback.
        try:_proc_read(Path('/proc',str(os.getpid()),'task',str(os.getpid()),'children'),65536)
        except FileNotFoundError:
            _linux_stat(os.getpid(),deadline);_PROC_STAT_CHILD_ADAPTER=True
        else:_PROC_STAT_CHILD_ADAPTER=False
    if not _PROC_STAT_CHILD_ADAPTER:
        raw=_proc_read(Path('/proc',str(pid),'task',str(pid),'children'),65536)
        need(time.monotonic()<deadline,'proc read deadline')
        return [int(v) for v in raw.split()]
    result=[];count=0
    for candidate in _proc_pids():
        count+=1;need(count<=_PROC_ENTRY_CAP,'bounded proc ancestry inventory cap')
        try:value=_linux_stat(candidate,deadline)
        except (FileNotFoundError,ProcessLookupError):continue
        if value['ppid']==pid:result.append(candidate)
    need(time.monotonic()<deadline,'proc scan deadline')
    return result


def _pidfd_exited(fd):
    import select
    poll=select.poll();poll.register(fd,select.POLLIN)
    events=poll.poll(0)
    need(not any(flags & (select.POLLERR|select.POLLNVAL) for _,flags in events),'pidfd readiness failure')
    return any(flags & select.POLLIN for _,flags in events)


_LINUX_WAIT_ALL_CHILDREN=0x40000000  # Linux __WALL includes clone and non-clone children.


def _linux_no_children(deadline):
    """Absence only: never consume a status or use an oracle-returned PID."""
    need(time.monotonic()<deadline,'no-child oracle deadline')
    need(signal.getsignal(signal.SIGCHLD)==signal.SIG_DFL,'incompatible SIGCHLD at no-child oracle')
    need(callable(getattr(os,'waitid',None)) and all(hasattr(os,key) for key in ('P_ALL','WEXITED','WNOHANG','WNOWAIT')),
         'required no-child oracle API unavailable')
    absent=False
    try:
        os.waitid(os.P_ALL,0,os.WEXITED|os.WNOHANG|os.WNOWAIT|_LINUX_WAIT_ALL_CHILDREN)
    except OSError as error:
        absent=error.errno==errno.ECHILD
    finally:
        need(time.monotonic()<deadline,'no-child oracle deadline')
        need(signal.getsignal(signal.SIGCHLD)==signal.SIG_DFL,'SIGCHLD changed at no-child oracle')
    need(absent,'kernel child absence not proved')


def _bounded_failure_detail(value, fallback, cap, ownership=False):
    """Detach fixed primitives and measure their actual pretty CRLF wrapper."""
    try:
        wrapper={'failure_detail':value}
        if ownership:wrapper={'ownership':wrapper}
        raw=(json.dumps(wrapper,sort_keys=True,indent=2,allow_nan=False)+'\n').replace('\n','\r\n').encode('utf-8')
        need(len(raw)<=cap,'failure detail cap')
        detached=json.loads(raw)
        return (detached['ownership'] if ownership else detached)['failure_detail']
    except BaseException:return dict(fallback)


def _linux_detail_unavailable():
    return dict(schema='qbrain-n49d-linux-identity-comparison-v1',site='observe-post-pidfd',complete=False,reason='detail-unavailable')


def _copy_linux_failure_detail(value):
    fallback=_linux_detail_unavailable()
    try:
        fields={'same_start','before_parent_matches_expected','after_parent_matches_expected','after_parent_matches_controller',
            'before_after_parent_equal','expected_parent_is_controller','parent_pin_present','candidate_was_already_known','final_parent_check_returned_true'}
        need(type(value) is dict,'detail mapping type')
        if value==fallback:return fallback
        need(set(value)==set(fallback)|fields and value['complete'] is True and
             value['schema']==fallback['schema'] and value['site']==fallback['site'] and
             value['reason'] in ('start-mismatch','parent-mismatch','start-and-parent-mismatch') and
             all(type(value[key]) is bool for key in fields),'detail fixed fields')
        return _bounded_failure_detail(value,fallback,1024,ownership=True)
    except BaseException:return fallback


def _linux_identity_detail(before,after,parent,controller,parent_pin):
    fallback=_linux_detail_unavailable()
    try:
        need(all(type(v) is int for v in (before['start'],after['start'],before['ppid'],after['ppid'],parent,controller)), 'detail types')
        same=before['start']==after['start'];linked=after['ppid']==parent
        value=dict(schema=fallback['schema'],site=fallback['site'],complete=True,
            reason='parent-mismatch' if same else ('start-mismatch' if linked else 'start-and-parent-mismatch'),
            same_start=same,before_parent_matches_expected=before['ppid']==parent,
            after_parent_matches_expected=linked,after_parent_matches_controller=after['ppid']==controller,
            before_after_parent_equal=before['ppid']==after['ppid'],expected_parent_is_controller=parent==controller,
            parent_pin_present=parent_pin is not None,candidate_was_already_known=False,final_parent_check_returned_true=True)
        return _copy_linux_failure_detail(value)
    except BaseException:return fallback


class _LinuxTree:
    def __init__(self):
        import ctypes
        need(signal.getsignal(signal.SIGCHLD)==signal.SIG_DFL,'incompatible SIGCHLD reaper disposition')
        need(hasattr(os,'pidfd_open') and hasattr(signal,'pidfd_send_signal'),'pidfd ownership unavailable')
        self.controller_pid=os.getpid()
        need(not _linux_children(self.controller_pid),'unmanaged pre-existing child makes ownership ambiguous')
        _linux_no_children(_proc_deadline())
        self.libc=ctypes.CDLL(None,use_errno=True);self.previous=ctypes.c_int()
        need(self.libc.prctl(37,ctypes.byref(self.previous),0,0,0)==0,'cannot read subreaper state')
        need(self.libc.prctl(36,1,0,0,0)==0,'cannot enable runner-local subreaper')
        self.known={};self.proc=None;self.restored=False

    def attach(self,proc):
        self.proc=proc;self.observe(proc.pid,os.getpid())

    def parent_current(self,parent,pin):
        if parent==os.getpid():
            need(pin is None,'unexpected interpreter parent pin');return True
        need(pin is not None and self.known.get(parent) is pin,'queued parent pin mismatch')
        if _pidfd_exited(pin['fd']):return False
        try:current=_linux_stat(parent)
        except (FileNotFoundError,ProcessLookupError):
            need(_pidfd_exited(pin['fd']),'live parent pidfd lost identity record');return False
        if _pidfd_exited(pin['fd']):return False
        need(current['start']==pin['start'],'owned parent identity changed')
        return True

    def observe(self,pid,parent,parent_pin=None):
        if not self.parent_current(parent,parent_pin):return None
        try:before=_linux_stat(pid)
        except (FileNotFoundError,ProcessLookupError):
            if pid in self.known:need(_pidfd_exited(self.known[pid]['fd']),'live pidfd lost identity record')
            return None
        if not self.parent_current(parent,parent_pin):return None
        need(before['ppid']==parent,'ambiguous descendant ancestry')
        if pid in self.known:
            need(self.known[pid]['start']==before['start'],'owned PID identity changed');return self.known[pid]
        try:fd=os.pidfd_open(pid,0)
        except ProcessLookupError:return None
        retained=False
        try:
            after=_linux_stat(pid)
            if not self.parent_current(parent,parent_pin):return None
            try:
                need(before['start']==after['start'] and after['ppid']==parent,'pidfd identity/ancestry mismatch')
            except ValueError as error:
                if str(error)=='pidfd identity/ancestry mismatch' and getattr(self,'failure_detail',None) is None:
                    self.failure_detail=_linux_detail_unavailable()
                    try:self.failure_detail=_linux_identity_detail(before,after,parent,self.controller_pid,parent_pin)
                    except BaseException:pass
                raise
            self.known[pid]=dict(fd=fd,start=after['start'])
            retained=True;return self.known[pid]
        except (FileNotFoundError,ProcessLookupError):
            need(_pidfd_exited(fd),'live pidfd lost identity record');return None
        finally:
            if not retained:os.close(fd)

    def active(self):
        # Only this interpreter's child lineage; exclusive launch audit is active.
        pending=[(pid,os.getpid(),None) for pid in _linux_children(os.getpid())];seen=set()
        while pending:
            pid,parent,parent_pin=pending.pop()
            if pid in seen:continue
            seen.add(pid);need(len(seen)<=1024,'owned child count cap')
            pin=self.observe(pid,parent,parent_pin)
            if pin is None or not self.parent_current(pid,pin):continue
            try:children=_linux_children(pid)
            except (FileNotFoundError,ProcessLookupError):
                need(_pidfd_exited(pin['fd']),'live pidfd lost child inventory');continue
            if self.parent_current(pid,pin):pending.extend((child,pid,pin) for child in children)
        alive=[]
        for pid,row in self.known.items():
            if not _pidfd_exited(row['fd']):alive.append(pid)
            elif self.proc is not None and pid!=self.proc.pid:
                try:
                    current=_linux_stat(pid)
                    need(current['start']==row['start'],'adopted child identity changed before reap')
                    need(signal.getsignal(signal.SIGCHLD)==signal.SIG_DFL,'SIGCHLD disposition changed during ownership')
                    if current['ppid']==os.getpid():os.waitpid(pid,os.WNOHANG)
                except (FileNotFoundError,ProcessLookupError,ChildProcessError):pass
        if self.proc is not None:self.proc.poll()
        return alive

    def terminate(self):
        self.active()
        for row in self.known.values():
            try:signal.pidfd_send_signal(row['fd'],signal.SIGKILL,None,0)
            except ProcessLookupError:pass

    def close(self):
        need(not self.active() and not _linux_children(os.getpid()),'owned children not reaped')
        _linux_no_children(_proc_deadline())
        need(self.libc.prctl(36,self.previous.value,0,0,0)==0,'cannot restore subreaper state')
        self.restored=True
        for row in self.known.values():os.close(row['fd'])
        self.known.clear()


def _windows_job_list_type(c):
    # Fixed Windows widths also make the off-platform API controls faithful.
    class ProcessList(c.Structure):
        _fields_=[('assigned',c.c_uint32),('listed',c.c_uint32),('pids',c.c_size_t*32)]
    return ProcessList


def _bounded_job_diagnostic(value):
    try:
        need(len((json.dumps(value,sort_keys=True,indent=2)+'\n').replace('\n',os.linesep).encode('utf-8'))<=8192,'metadata_cap')
        return value
    except BaseException:
        return dict(complete=False,observation='unknown',error='metadata_cap',members=[])



def _image_sample(status='not_selected',index=None,name=None,name_hash=None,win32=None):
    """Only six fixed redacted fields; malformed detail cannot affect ownership."""
    valid_index=type(index) is int and 0<=index<32
    fallback=dict(member_index=index if valid_index else None,status='metadata_cap',
                  basename=None,basename_sha256=None,race='non_atomic',win32=None)
    try:
        need(status in ('not_selected','sampled','redacted_basename','query_failed','buffer_limit',
                        'invalid_result','deadline','api_exception','metadata_cap'),'image status')
        need(index is None or valid_index,'image index')
        if status=='not_selected':need(index is None and name is None and name_hash is None and win32 is None,'image empty')
        elif status in ('sampled','redacted_basename'):
            need(valid_index and type(name_hash) is str and re.fullmatch('[0-9a-f]{64}',name_hash) and win32 is None,'image name hash')
            need((status=='sampled' and type(name) is str and re.fullmatch('[A-Za-z0-9_.-]{1,64}',name) and name not in ('.','..')) or
                 (status=='redacted_basename' and name is None),'image name')
        elif status in ('query_failed','buffer_limit'):
            need(valid_index and name is None and name_hash is None and type(win32) is int and 0<=win32<=0xffffffff and
                 ((win32==122)==(status=='buffer_limit')),'image error')
        else:need(name is None and name_hash is None and win32 is None,'image unavailable')
        value=dict(member_index=index,status=status,basename=name,basename_sha256=name_hash,race='non_atomic',win32=win32)
        need(len((json.dumps(value,sort_keys=True,indent=2)+'\n').replace('\n','\r\n').encode('utf-8'))<=512,'image cap')
        return value
    except BaseException:return fallback


def _windows_image_eligible(row):
    return (isinstance(row,dict) and row.get('root') is False and 'error' not in row and
            all(type(row.get(key)) is int and row[key]==value
                for key,value in (('wait_before',258),('exit_code',259),('wait_after',258))))


def _windows_image_name(units,count):
    need(type(count) is int and 1<=count<1024 and len(units)==1024,'invalid_result')
    need(units[count]==0 and all(type(x) is int and 0<x<=0xffff for x in units[:count]),'invalid_result')
    last=max((i for i in range(count) if units[i] in (47,92)),default=-1)
    raw=b''.join(x.to_bytes(2,'little') for x in units[last+1:count])
    name=raw.decode('utf-16le',errors='strict')
    need(name not in ('','.','..'),'invalid_result')
    name_hash=hashlib.sha256(raw).hexdigest()
    return name if re.fullmatch('[A-Za-z0-9_.-]{1,64}',name) else None,name_hash


class _WindowsTree:
    def __init__(self):
        import ctypes as c
        from ctypes import wintypes as w
        self.c=c;self.w=w;self.k=c.WinDLL('kernel32',use_last_error=True);self.proc=None;self.assigned=False
        self.last_accounting=None;self.ProcessList=_windows_job_list_type(c)
        need(c.sizeof(self.ProcessList)==8+32*c.sizeof(c.c_size_t),'private job list ABI mismatch')
        class Basic(c.Structure):
            _fields_=[('PerProcessUserTimeLimit',c.c_longlong),('PerJobUserTimeLimit',c.c_longlong),('LimitFlags',w.DWORD),('MinimumWorkingSetSize',c.c_size_t),('MaximumWorkingSetSize',c.c_size_t),('ActiveProcessLimit',w.DWORD),('Affinity',c.c_size_t),('PriorityClass',w.DWORD),('SchedulingClass',w.DWORD)]
        class IO(c.Structure):_fields_=[(n,c.c_ulonglong) for n in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
        class Extended(c.Structure):_fields_=[('BasicLimitInformation',Basic),('IoInfo',IO),('ProcessMemoryLimit',c.c_size_t),('JobMemoryLimit',c.c_size_t),('PeakProcessMemoryUsed',c.c_size_t),('PeakJobMemoryUsed',c.c_size_t)]
        class Accounting(c.Structure):_fields_=[('TotalUserTime',c.c_longlong),('TotalKernelTime',c.c_longlong),('ThisPeriodTotalUserTime',c.c_longlong),('ThisPeriodTotalKernelTime',c.c_longlong),('TotalPageFaultCount',w.DWORD),('TotalProcesses',w.DWORD),('ActiveProcesses',w.DWORD),('TotalTerminatedProcesses',w.DWORD)]
        class Thread(c.Structure):_fields_=[('dwSize',w.DWORD),('cntUsage',w.DWORD),('th32ThreadID',w.DWORD),('th32OwnerProcessID',w.DWORD),('tpBasePri',w.LONG),('tpDeltaPri',w.LONG),('dwFlags',w.DWORD)]
        self.Accounting=Accounting;self.Thread=Thread
        signatures={'CreateJobObjectW':([c.c_void_p,w.LPCWSTR],w.HANDLE),'SetInformationJobObject':([w.HANDLE,c.c_int,c.c_void_p,w.DWORD],w.BOOL),'SetHandleInformation':([w.HANDLE,w.DWORD,w.DWORD],w.BOOL),'CloseHandle':([w.HANDLE],w.BOOL),'OpenProcess':([w.DWORD,w.BOOL,w.DWORD],w.HANDLE),'AssignProcessToJobObject':([w.HANDLE,w.HANDLE],w.BOOL),'CreateToolhelp32Snapshot':([w.DWORD,w.DWORD],w.HANDLE),'Thread32First':([w.HANDLE,c.POINTER(Thread)],w.BOOL),'Thread32Next':([w.HANDLE,c.POINTER(Thread)],w.BOOL),'OpenThread':([w.DWORD,w.BOOL,w.DWORD],w.HANDLE),'ResumeThread':([w.HANDLE],w.DWORD),'GetProcessIdOfThread':([w.HANDLE],w.DWORD),'QueryInformationJobObject':([w.HANDLE,c.c_int,c.c_void_p,w.DWORD,c.c_void_p],w.BOOL),'TerminateJobObject':([w.HANDLE,w.UINT],w.BOOL)}
        for name,(args,ret) in signatures.items():getattr(self.k,name).argtypes=args;getattr(self.k,name).restype=ret
        for name,(args,ret) in {'IsProcessInJob':([w.HANDLE,w.HANDLE,c.POINTER(w.BOOL)],w.BOOL),
                'WaitForSingleObject':([w.HANDLE,w.DWORD],w.DWORD),
                'GetExitCodeProcess':([w.HANDLE,c.POINTER(w.DWORD)],w.BOOL)}.items():
            getattr(self.k,name).argtypes=args;getattr(self.k,name).restype=ret
        self.job=self.k.CreateJobObjectW(None,None);need(bool(self.job),'CreateJobObject failed')
        try:
            need(self.k.SetHandleInformation(self.job,1,0),'noninheritable job handle failed')
            info=Extended();info.BasicLimitInformation.LimitFlags=0x2000
            need(self.k.SetInformationJobObject(self.job,9,c.byref(info),c.sizeof(info)),'kill-on-close job policy failed')
        except BaseException:self.k.CloseHandle(self.job);self.job=None;raise

    def attach(self,proc):
        self.proc=proc;c=self.c;k=self.k
        process=k.OpenProcess(0x0100|0x0001,False,proc.pid);need(bool(process),'OpenProcess for private job failed')
        try:need(k.AssignProcessToJobObject(self.job,process),'private nested job assignment failed');self.assigned=True
        finally:need(k.CloseHandle(process),'owned process handle close failed')
        snapshot=k.CreateToolhelp32Snapshot(0x00000004,0)
        need(snapshot not in (None,c.c_void_p(-1).value),'thread snapshot failed')
        threads=[]
        try:
            entry=self.Thread();entry.dwSize=c.sizeof(entry);ok=k.Thread32First(snapshot,c.byref(entry))
            while ok:
                if entry.th32OwnerProcessID==proc.pid:threads.append(entry.th32ThreadID)
                entry.dwSize=c.sizeof(entry);c.set_last_error(0);ok=k.Thread32Next(snapshot,c.byref(entry))
            need(c.get_last_error()==18,'thread inventory API failure')
        finally:need(k.CloseHandle(snapshot),'thread snapshot close failed')
        need(len(threads)==1,'suspended primary thread inventory ambiguous')
        thread=k.OpenThread(0x0002|0x0800,False,threads[0]);need(bool(thread),'OpenThread failed')
        try:
            need(k.GetProcessIdOfThread(thread)==proc.pid,'opened thread is not owned primary thread')
            need(k.ResumeThread(thread)==1,'primary thread resume failed')
        finally:need(k.CloseHandle(thread),'primary thread handle close failed')

    def active(self):
        if not self.assigned:return [self.proc.pid] if self.proc is not None and self.proc.poll() is None else []
        value=self.Accounting();need(self.k.QueryInformationJobObject(self.job,1,self.c.byref(value),self.c.sizeof(value),None),'private job accounting failed')
        self.last_accounting=dict(total=value.TotalProcesses,active=value.ActiveProcesses,terminated=value.TotalTerminatedProcesses)
        return list(range(value.ActiveProcesses))

    def observe_member(self,handle,deadline):
        """Observe an already verified, pinned private-job member; never by PID."""
        row={};step='wait_before'
        try:
            need(time.monotonic()<deadline,'deadline')
            row['wait_before']=int(self.k.WaitForSingleObject(handle,0));error=int(self.c.get_last_error())
            need(time.monotonic()<deadline,'deadline')
            if row['wait_before'] not in (0,258):row.update(error=step,win32=error);return row
            step='exit_code';value=self.w.DWORD()
            need(time.monotonic()<deadline,'deadline')
            ok=self.k.GetExitCodeProcess(handle,self.c.byref(value));error=int(self.c.get_last_error())
            need(time.monotonic()<deadline,'deadline')
            if not ok:row.update(error=step,win32=error);return row
            row['exit_code']=int(value.value);step='wait_after'
            need(time.monotonic()<deadline,'deadline')
            row['wait_after']=int(self.k.WaitForSingleObject(handle,0));error=int(self.c.get_last_error())
            need(time.monotonic()<deadline,'deadline')
            if row['wait_after'] not in (0,258):row.update(error=step,win32=error)
            elif row['wait_before']==0 and row['wait_after']!=0:row['error']='conflicting_states'
            elif row['wait_after']==258 and row['exit_code']!=259:row['error']='conflicting_states'
        except BaseException as error:
            row['error']='deadline' if isinstance(error,ValueError) and str(error)=='deadline' else 'api_exception'
        return row


    def sample_image(self,handle,index,deadline):
        """One name query on the existing verified member handle, never a PID."""
        c=self.c;buffer=None;phase='binding';value=_image_sample('api_exception',index)
        try:
            need(time.monotonic()<deadline,'deadline')
            need(type(index) is int and 0<=index<32,'invalid_result')
            # Resolve and validate only inside this failure-only unavailable boundary.
            need(c.sizeof(c.c_void_p)==c.sizeof(c.c_size_t)==8 and
                 c.sizeof(c.c_uint16)==2 and c.sizeof(c.c_uint32)==c.sizeof(c.c_int32)==4,'image ABI')
            query=self.k.QueryFullProcessImageNameW
            query.argtypes=[c.c_void_p,c.c_uint32,c.POINTER(c.c_uint16),c.POINTER(c.c_uint32)]
            query.restype=c.c_int32
            buffer=(c.c_uint16*1024)();length=c.c_uint32(1024)
            need(time.monotonic()<deadline,'deadline')
            phase='query'
            ok=query(handle,0,buffer,c.byref(length))
            error=c.get_last_error() if not ok else None
            need(time.monotonic()<deadline,'deadline')
            phase='parse'
            need(type(ok) is int,'invalid_result')
            if not ok:
                need(type(error) is int and 0<=error<=0xffffffff,'invalid_result')
                value=_image_sample('buffer_limit' if error==122 else 'query_failed',index,win32=error)
            else:
                name,name_hash=_windows_image_name(list(buffer),length.value)
                need(time.monotonic()<deadline,'deadline')
                value=_image_sample('sampled' if name is not None else 'redacted_basename',index,name,name_hash)
            need(time.monotonic()<deadline,'deadline')
        except BaseException as error:
            status='deadline' if isinstance(error,ValueError) and str(error)=='deadline' else (
                'invalid_result' if phase=='parse' and isinstance(error,(UnicodeError,ValueError)) else 'api_exception')
            value=_image_sample(status,index)
        finally:
            if buffer is not None:
                try:c.memset(buffer,0,c.sizeof(buffer))
                except BaseException:value=_image_sample('api_exception',index)
        if time.monotonic()>=deadline:value=_image_sample('deadline',index)
        return value

    def diagnostic(self,cleanup_deadline):
        """One bounded observation, with no effect on the selected failure."""
        started=time.monotonic();deadline=min(cleanup_deadline,started+.100)
        value=dict(complete=False,observation='unknown',trigger=self.last_accounting,handles_closed=True,members=[],image_sample=_image_sample())
        image_selected=False
        step='accounting'
        try:
            need(self.assigned and bool(self.job),'invalid_job')
            need(time.monotonic()<deadline,'deadline')
            accounting=self.Accounting()
            ok=self.k.QueryInformationJobObject(self.job,1,self.c.byref(accounting),self.c.sizeof(accounting),None)
            error=int(self.c.get_last_error());need(time.monotonic()<deadline,'deadline')
            if not ok:value.update(error=step,win32=error);return _bounded_job_diagnostic(value)
            value['accounting']=dict(total=accounting.TotalProcesses,active=accounting.ActiveProcesses,terminated=accounting.TotalTerminatedProcesses)
            step='process_list';listing=self.ProcessList();length=self.w.DWORD()
            need(time.monotonic()<deadline,'deadline')
            ok=self.k.QueryInformationJobObject(self.job,3,self.c.byref(listing),self.c.sizeof(listing),self.c.byref(length))
            error=int(self.c.get_last_error());need(time.monotonic()<deadline,'deadline')
            value.update(assigned=int(listing.assigned),listed=int(listing.listed))
            if not ok:value.update(error=step,win32=error);return _bounded_job_diagnostic(value)
            need(0<=listing.listed==listing.assigned<=32 and
                 8+listing.listed*self.c.sizeof(self.c.c_size_t)<=length.value<=self.c.sizeof(listing),'invalid_list')
            pids=list(listing.pids[:listing.listed])
            need(len(set(pids))==len(pids) and all(0<pid<=0xffffffff for pid in pids),'invalid_list')
            for pid in pids:
                need(time.monotonic()<deadline,'deadline')
                row=dict(pid=int(pid));value['members'].append(row);handle=None
                try:
                    step='open';handle=self.k.OpenProcess(0x00101000,False,pid);error=int(self.c.get_last_error())
                    need(time.monotonic()<deadline,'deadline')
                    if not handle:row.update(error=step,win32=error);continue
                    step='membership';member=self.w.BOOL()
                    need(time.monotonic()<deadline,'deadline')
                    ok=self.k.IsProcessInJob(handle,self.job,self.c.byref(member));error=int(self.c.get_last_error())
                    need(time.monotonic()<deadline,'deadline')
                    if not ok:row.update(error=step,win32=error);continue
                    if not member.value:row['error']='membership_mismatch';continue
                    row['root']=pid==self.proc.pid
                    row.update(self.observe_member(handle,deadline))
                    if not image_selected and _windows_image_eligible(row):
                        image_selected=True
                        value['image_sample']=self.sample_image(handle,len(value['members'])-1,deadline)
                finally:
                    if handle:
                        try:
                            ok=self.k.CloseHandle(handle);error=int(self.c.get_last_error())
                            if not ok:row.update(error='close',win32=error);value['handles_closed']=False
                        except BaseException:row['error']='close_exception';value['handles_closed']=False
                        if time.monotonic()>=deadline:row['error']='deadline'
                need(time.monotonic()<deadline,'deadline')
            value['complete']=not any('error' in row for row in value['members'])
            if value['complete']:
                value['observation']='live_member_observed' if any(row['wait_before']==258 for row in value['members']) else 'no_live_member_observed_in_complete_snapshot'
        except BaseException as error:
            value['error']=str(error) if isinstance(error,ValueError) and str(error) in ('deadline','invalid_list','invalid_job') else 'api_exception'
            value['complete']=False;value['observation']='unknown'
        return _bounded_job_diagnostic(value)

    def terminate(self):
        if self.assigned:need(self.k.TerminateJobObject(self.job,1),'private job termination failed')
        elif self.proc is not None and self.proc.poll() is None:self.proc.kill()

    def close(self):
        need(not self.active(),'private job still has active members')
        if self.job:need(self.k.CloseHandle(self.job),'private job close failed');self.job=None


class OwnedChildError(ValueError):
    def __init__(self,message,owner):super().__init__(message);self.owner=owner


class OwnedChild:
    """One owned command, no overlapping/unmanaged launches in this interpreter."""
    def __init__(self,argv,cwd,env,stdin,stdout_path,stderr_path,timeout,stream_cap):
        global _ACTIVE_OWNER,_AUDIT_INSTALLED,_LAUNCH_THREAD,_LAUNCH_ARGV
        self.started=time.monotonic();self.deadline=self.started+timeout;self.scan_deadline=self.deadline;self.proc=None;self.tree=None
        self.paths=[Path(stdout_path),Path(stderr_path)];self.stream_cap=stream_cap;self.result=None;self.stable=False
        self.readers=[];self.overflow=threading.Event();self.errors=[];self.locked=False;self.job_diagnostic=None
        for path in self.paths:path.parent.mkdir(parents=True,exist_ok=True);path.touch(exist_ok=False)
        try:
            need(timeout>0 and stream_cap>0,'invalid owned deadline/budget')
            need(threading.current_thread() is threading.main_thread(),'owned launch requires serial main-thread caller')
            need(_OWNER_LOCK.acquire(blocking=False),'concurrent owned process rejected');self.locked=True
            _ACTIVE_OWNER=self
            if not _AUDIT_INSTALLED:sys.addaudithook(_audit_launch);_AUDIT_INSTALLED=True
            self.tree=_WindowsTree() if os.name=='nt' else _LinuxTree()
            _LAUNCH_THREAD=threading.get_ident();_LAUNCH_ARGV=list(map(str,argv))
            try:
                self.proc=subprocess.Popen(_LAUNCH_ARGV,cwd=cwd,env=env,stdin=stdin,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                    close_fds=True,bufsize=0,start_new_session=os.name!='nt',creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP|0x00000004) if os.name=='nt' else 0)
            finally:_LAUNCH_THREAD=None;_LAUNCH_ARGV=None
            self.tree.proc=self.proc
            self.tree.attach(self.proc)
            for pipe,path in zip((self.proc.stdout,self.proc.stderr),self.paths):
                thread=threading.Thread(target=self._drain,args=(pipe,path),daemon=True);self.readers.append(thread);thread.start()
            self.check_budget()
        except BaseException as error:
            self._end(str(error));raise OwnedChildError(str(error),self) from error

    def _drain(self,pipe,path):
        try:
            with path.open('wb',buffering=0) as out:
                while data:=pipe.read(65536):
                    remaining=self.stream_cap-out.tell()
                    if len(data)>remaining:out.write(data[:max(0,remaining)]);self.overflow.set();break
                    out.write(data)
        except BaseException as error:self.errors.append(str(error));self.overflow.set()
        finally:pipe.close()

    def _diagnose_lingering(self,cleanup_deadline):
        if self.job_diagnostic is not None or not hasattr(self.tree,'diagnostic'):return
        self.job_diagnostic=dict(complete=False,observation='unknown',error='api_exception',members=[])
        try:self.job_diagnostic=_bounded_job_diagnostic(self.tree.diagnostic(cleanup_deadline))
        except BaseException:pass

    def _end(self,failure=None,intentional=False):
        global _ACTIVE_OWNER
        if self.result is not None:return self.result
        cleanup_deadline=time.monotonic()+2 if failure else self.deadline
        self.scan_deadline=cleanup_deadline;self.stable=False
        root_exit=None;no_root_failure=self.proc is None and bool(failure)
        close_attempted=False;close_returned=False;close_in_budget=False
        cleanup_ok=False;cleanup_error=None;capture_error=None
        streams={'stdout':None,'stderr':None}
        def budget(message):
            nonlocal failure
            if time.monotonic()>=cleanup_deadline:
                if not failure and time.monotonic()>=self.deadline:failure='timeout'
                raise ValueError(message)
        def cleanup():
            nonlocal root_exit,close_attempted,close_returned,close_in_budget,cleanup_deadline,failure
            budget('owned cleanup deadline exceeded')
            if self.tree is None:
                need(no_root_failure,'owned root/tree unavailable');return
            if failure or intentional:
                self.tree.terminate();budget('owned cleanup deadline exceeded')
            while True:
                budget('owned cleanup deadline exceeded')
                if self.proc is not None and root_exit is None:root_exit=self.proc.poll()
                budget('owned cleanup deadline exceeded')
                alive=self.tree.active();budget('owned cleanup deadline exceeded')
                need(self.proc is not None or no_root_failure,'owned root unavailable')
                if alive and not failure and not intentional:
                    failure='lingering-descendant'
                    cleanup_deadline=min(cleanup_deadline,time.monotonic()+2);self.scan_deadline=cleanup_deadline
                    self._diagnose_lingering(cleanup_deadline)
                    raise ValueError(failure)
                if not alive and (root_exit is not None or no_root_failure):break
                if alive and (failure or intentional):
                    self.tree.terminate();budget('owned cleanup deadline exceeded')
                time.sleep(min(.005,max(0,cleanup_deadline-time.monotonic())))
            budget('owned cleanup deadline exceeded')
            close_attempted=True
            self.tree.close();close_returned=True
            budget('owned cleanup deadline exceeded');close_in_budget=True
        if failure=='lingering-descendant':self._diagnose_lingering(cleanup_deadline)
        try:
            if self.proc is not None and not self.readers:
                for pipe in (self.proc.stdout,self.proc.stderr):
                    if pipe is not None:pipe.close()
            cleanup();cleanup_ok=True
        except BaseException as error:
            cleanup_error=str(error);failure=failure or 'cleanup-failed'
            # A close attempt can partially release ownership. Never touch that
            # tree again; only pre-close errors permit this bounded fallback.
            if not close_attempted:
                try:cleanup();cleanup_ok=True
                except BaseException as retry_error:cleanup_error+='; '+str(retry_error)
        for thread in self.readers:
            try:
                budget('owned capture deadline exceeded')
                thread.join(max(0,cleanup_deadline-time.monotonic()))
                budget('owned capture deadline exceeded')
            except BaseException:
                capture_error='capture-deadline' if time.monotonic()>=cleanup_deadline else 'reader-join-failed'
        try:readers_done=not any(t.is_alive() for t in self.readers)
        except BaseException:readers_done=False;capture_error=capture_error or 'reader-state-unavailable'
        for key,path in zip(('stdout','stderr'),self.paths):
            if time.monotonic()>=cleanup_deadline:
                capture_error=capture_error or 'capture-deadline';continue
            try:
                streams[key]=descriptor(path)
                if time.monotonic()>=cleanup_deadline:capture_error=capture_error or 'capture-deadline'
            except BaseException:
                reason=key+'-unavailable'
                capture_error='both-unavailable' if capture_error=='stdout-unavailable' and key=='stderr' else (capture_error or reason)
        cleanup_ok=cleanup_ok and (self.tree is None or (close_returned and close_in_budget)) and readers_done and capture_error is None
        self.stable=cleanup_ok
        if not self.stable:failure=failure or ('timeout' if time.monotonic()>=self.deadline else 'capture-not-finalized')
        if self.overflow.is_set() or self.errors:failure=failure or 'output-limit'
        if not failure and time.monotonic()>=self.deadline:failure='timeout'
        value=dict(classification=failure or ('stopped' if intentional else 'passed'),exit=root_exit,
            process_backend='windows-private-job' if os.name=='nt' else ('linux-stat-pidfd-subreaper' if _PROC_STAT_CHILD_ADAPTER else 'linux-children-pidfd-subreaper'),
            root_pid=self.proc.pid if self.proc else None,owned_tree_empty=cleanup_ok,
            cleanup_ok=cleanup_ok,cleanup_error=cleanup_error,stable=self.stable,readers_done=readers_done,
            elapsed_seconds=round(time.monotonic()-self.started,6),stdout=streams['stdout'],stderr=streams['stderr'])
        if capture_error is not None:value['capture_error']=capture_error
        if self.job_diagnostic is not None:value['job_diagnostic']=self.job_diagnostic
        if failure and isinstance(self.tree,_LinuxTree):
            try:
                if getattr(self.tree,'failure_detail',None) is not None:
                    value['failure_detail']=_linux_detail_unavailable()
                    value['failure_detail']=_copy_linux_failure_detail(self.tree.failure_detail)
            except BaseException:value['failure_detail']=_linux_detail_unavailable()
        if time.monotonic()>=cleanup_deadline:
            failure=failure or 'timeout';self.stable=False;cleanup_ok=False
            value.update(classification=failure,owned_tree_empty=False,cleanup_ok=False,stable=False)
            value.setdefault('capture_error','capture-deadline')
        value['elapsed_seconds']=round(time.monotonic()-self.started,6)
        self.result=value
        if cleanup_ok and readers_done and self.locked:
            _ACTIVE_OWNER=None;self.locked=False;_OWNER_LOCK.release()
        return value

    def check_budget(self):
        failure='output-limit' if self.overflow.is_set() or self.errors else ('timeout' if time.monotonic()>=self.deadline else None)
        if failure:self._end(failure);raise OwnedChildError(failure,self)

    def wait(self,expected=0,timeout=None):
        if timeout is not None:self.deadline=min(self.deadline,self.started+timeout);self.scan_deadline=self.deadline
        if self.result is not None:
            if self.result['classification']!='passed':raise OwnedChildError(self.result['classification'],self)
            return self.result
        try:
            while True:
                self.check_budget();code=self.proc.poll()
                active=self.tree.active()
                if code is not None:
                    if active:raise ValueError('lingering-descendant')
                    if code!=expected:raise ValueError('nonzero child exit')
                    if not any(t.is_alive() for t in self.readers):break
                time.sleep(.005)
            value=self._end()
            if value['classification']!='passed':raise OwnedChildError(value['classification'],self)
            return value
        except BaseException as error:
            self._end('timeout' if str(error)!='lingering-descendant' and time.monotonic()>=self.deadline else str(error));raise OwnedChildError(self.result['classification'],self) from error

    def stop(self,reason='intentional_shutdown'):
        if self.result is not None:return self.result
        failure='timeout' if time.monotonic()>=self.deadline else None
        result=self._end(failure,intentional=True);result['stop_reason']=reason
        if result['classification']!='stopped':raise OwnedChildError(result['classification'],self)
        return result


class Recorder:
    def __init__(self, root, identity, required, environment, cwd, stream_cap=8*MIB):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=False)
        self.identity = identity; same_identity(identity, identity)
        self.required = list(required); need(len(set(required)) == len(required), 'duplicate required stage')
        self.environment = environment; self.cwd = Path(cwd); self.stream_cap = stream_cap
        self.stages = []; self.binary_pins = {}

    def run(self, name, argv, timeout, binaries=(), produced=(), reports=(), check=None):
        start=time.monotonic();deadline=start+timeout
        need(name in self.required and name not in self.stages, 'unexpected/duplicate stage')
        folder = self.root / 'stages' / name; folder.mkdir(parents=True)
        self.stages.append(name)
        before={}
        result = dict(schema='qbrain-n49d-stage-v1',name=name,identity=self.identity,
                      argv=[str(a) for a in argv],cwd=str(self.cwd),timeout_seconds=timeout,
                      stream_limit=self.stream_cap,exit=None,classification='incomplete',
                      requested_reports=[Path(p).relative_to(self.root).as_posix() for p in reports],
                      binaries_before=before,binaries_after={},runtime_options={k:self.environment[k] for k in ('ASAN_OPTIONS','UBSAN_OPTIONS') if k in self.environment})
        failure=None;child=None
        streams=[folder/'stdout.bin',folder/'stderr.bin']
        def fail(error):
            nonlocal failure,child
            failure=failure or str(error);result['classification']=failure
            if isinstance(error,OwnedChildError):child=error.owner
            if child is not None:
                result['ownership']=child.result;result['exit']=child.result.get('exit') if child.result else None
        def retain_failed():
            result.setdefault('ownership',None)
            terminal=result.get('ownership') or {}
            for key in ('stdout','stderr'):result.setdefault(key,terminal.get(key))
            result['available_reports']={**result.get('reports',{}),**result.get('available_reports',{})}
            self.failed_result=result
        try:
            for p in binaries:before[str(p)]=descriptor(p)
            for p,value in before.items():
                need(self.binary_pins.setdefault(p,value)==value,'binary mutation before stage')
            need(time.monotonic()<deadline,'timeout during stage setup')
            child=OwnedChild(result['argv'],self.cwd,self.environment,subprocess.DEVNULL,*streams,deadline-time.monotonic(),self.stream_cap)
            child.deadline=deadline;child.scan_deadline=deadline
            terminal=child.wait()
            result['exit']=terminal['exit'];result['ownership']=terminal
            after=result['binaries_after']
            for p in list(binaries)+list(produced):after[str(p)]=descriptor(p)
            need(all(after[p] == value for p,value in before.items()), 'binary mutation during stage')
            for p,value in after.items():
                need(self.binary_pins.setdefault(p,value) == value, 'binary identity swapped')
            result['reports']={}
            for p in reports:result['reports'][Path(p).relative_to(self.root).as_posix()]=descriptor(p)
            if check: check()
            need(time.monotonic()<deadline,'timeout during stage finalization')
            result['classification']='passed'
        except Exception as error:fail(error)
        if failure is None:
            try:
                result['available_reports']={}
                for p in reports:
                    if Path(p).is_file():result['available_reports'][Path(p).relative_to(self.root).as_posix()]=descriptor(p)
                result['stdout']=descriptor(streams[0]);result['stderr']=descriptor(streams[1])
                need(time.monotonic()<deadline,'timeout during evidence finalization')
            except Exception as error:fail(error)
        result['elapsed_seconds']=round(time.monotonic()-start,3)
        if failure is not None:retain_failed()
        try:
            dump(folder/'result.json',result)
            if failure is None and time.monotonic()>=deadline:
                fail(ValueError('timeout during result write'));retain_failed();dump(folder/'result.json',result)
        except Exception as error:
            fail(error);retain_failed();result['evidence_error']='result-write-unavailable'
            raise ValueError(f'{name}: {failure}; result evidence unavailable') from error
        need(result['classification']=='passed',f'{name}: {failure}')
        return result

    def finish(self, source_before, source_after):
        need(self.stages == self.required, 'missing/duplicate/out-of-order required stage')
        need(source_before == source_after, 'source mutation after capture')
        for p,value in self.binary_pins.items():
            need(descriptor(p) == value, 'binary mutation after capture')
        result = dict(schema='qbrain-n49d-qualification-v1',passed=True,identity=self.identity,
                      required=self.required,stages=self.stages,binaries=self.binary_pins,locations=getattr(self,'locations',None),
                      source_before=source_before,source_after=source_after,
                      native_http='required-and-executed' if self.identity['job_key'].startswith('windows') else 'not-applicable-non-Windows-stub',
                      acceptance='native evidence only; independent outcome acceptance pending')
        dump(self.root/'qualification.json',result)
        validate_recordings(lambda p:(self.root/p).read_bytes(), self.identity, self.required)
        return result


def validate_semantics(read, expected, result):
    job=expected['job_key']
    for mode in ('normal','optimized'):
        checks=json.loads(read('stages/selftest-'+mode+'/stdout.bin'))
        need(checks.get('passed') is True and checks.get('python_optimized')==(mode=='optimized') and
             checks.get('controls') and all(c.get('passed') is True for c in checks['controls']), 'source controls semantic failure')
        if job.startswith('linux'):
            need(checks.get('linux_reader_backend')=='native-children','native Linux children-interface controls required')
    if job=='linux-sanitizers':
        effective=json.loads(read('reports/sanitizer-effective.json'));validate_sanitizer_flags(effective)
        for name in ('sanitize-mcp','sanitize-directory'):
            stage=json.loads(read('stages/'+name+'/result.json'))
            need(read('stages/'+name+'/stderr.bin')==b'' and stage.get('runtime_options')==effective['runtime_options'],
                 'sanitizer diagnostics/options mismatch')
        return
    if job!='windows-msvc':
        names=ctest_values(json.loads(read('stages/ctest-inventory/stdout.bin')),read('reports/ctest.xml'))
        need(json.loads(read('stages/ctest-completeness/stdout.bin'))==names,'CTest completeness semantic mismatch')
    if job.startswith('windows'):
        name='direct-tests' if job=='windows-msvc' else 'canonical-run'
        groups=native_groups((ROOT/'tests/test_main.cpp').read_text(encoding='utf-8'),read('stages/'+name+'/stdout.bin').decode('utf-8',errors='replace'))
        need(json.loads(read('stages/canonical-groups/stdout.bin'))==groups,'canonical group semantic mismatch')
    for mode in ('normal','optimized'):
        directory=json.loads(read('reports/directory_search-'+mode+'/RESULT.json'))
        need(directory.get('passed') is True and directory.get('checks') and all(c.get('passed') is True for c in directory['checks']) and
             directory.get('check_count')==len(directory['checks']) and directory.get('command_count')==len(directory.get('commands',[]))>0,
             'directory report semantic failure')
        context=json.loads(read('reports/context_process-'+mode+'.json'))
        need(context.get('format_version')==1 and isinstance(context.get('checks'),int) and context['checks']>0 and
             context.get('provider_calls')==0,'context report semantic failure')
        named=json.loads(read('reports/named_arguments-'+mode+'.json'))
        need(named.get('failed')==0 and named.get('checks') and all(c.get('passed') is True for c in named['checks']) and
             named.get('passed')==len(named['checks']) and named.get('command_count')==len(named.get('commands',[]))>0,
             'named-argument report semantic failure')
        stage=json.loads(read('stages/named_arguments-'+mode+'/result.json'))
        need(named.get('binary_sha256') in {v['sha256'] for v in stage['binaries_before'].values()},'named-argument binary mismatch')
        if job=='windows-cmake':
            report=json.loads(read('reports/winhttp-'+mode+'.json'))
            stage=json.loads(read('stages/winhttp-'+mode+'/result.json'))
            need(report.get('result')=='PASS' and report.get('native_windows') is True and report.get('checks') and
                 report.get('check_count')==len(report['checks']) and report.get('source_commit')==expected['commit'] and
                 report.get('probe_sha256') in {v['sha256'] for v in stage['binaries_before'].values()}, 'WinHTTP semantic failure')


def changed_source_members(paths):
    need(paths is not None,'complete evidence inventory required')
    names=list(paths)
    need(all(isinstance(p,str) for p in names),'invalid evidence path inventory')
    expected=['source/changed/'+p for p in sorted(source_guard.ALLOW)]
    need(sorted(p for p in names if p.startswith('source/changed/'))==expected,'fixed changed source leaf inventory mismatch')
    return expected


def validate_recordings(read, expected, required=None, *, files=None):
    """Same fail-closed recorder contract is checked before packaging and after download."""
    result = json.loads(read('qualification.json'))
    same_identity(result['identity'],expected)
    full_contract = required is None
    required = required if required is not None else required_stages(expected['job_key'])
    need(result.get('passed') is True and result['required'] == required and result['stages'] == required,
         'missing/duplicate required stage')
    need(len(required) == len(set(required)), 'duplicate required stages')
    need(result['source_before'] == result['source_after'], 'source identity mutated')
    binary_pins = result['binaries']
    contracts=stage_contract(expected,result['locations']) if full_contract else None
    for name in required:
        folder = 'stages/'+name+'/'
        stage = json.loads(read(folder+'result.json'))
        same_identity(stage['identity'], expected)
        need(stage['name'] == name and stage['classification'] == 'passed' and stage['exit'] == 0,
             'failed/incomplete stage')
        need(isinstance(stage['argv'],list) and bool(stage['argv']), 'stage command missing')
        requested=stage.get('requested_reports')
        need(isinstance(requested,list) and len(requested)==len(set(requested)) and
             set(stage.get('reports',{}))==set(requested),'requested report inventory mismatch')
        if contracts is not None:
            spec=contracts[name]
            ownership=stage.get('ownership',{})
            need(ownership.get('classification')=='passed' and ownership.get('cleanup_ok') is True and
                 ownership.get('stable') is True and ownership.get('readers_done') is True and ownership.get('exit')==0, 'stage ownership proof missing')
            need(ownership.get('stdout')==stage['stdout'] and ownership.get('stderr')==stage['stderr'], 'stage finalized stream binding mismatch')
            need(stage['argv']==spec['argv'] and stage['timeout_seconds']==spec['timeout_seconds'] and
                 stage['cwd']==result['locations']['source'], 'fixed stage command mismatch')
            need(requested==spec['reports'], 'fixed required report inventory mismatch')
            need(sorted(stage['binaries_before'])==spec['binaries_before'] and sorted(stage['binaries_after'])==spec['binaries_after'], 'fixed binary inventory mismatch')
        for stream in ('stdout','stderr'):
            data = read(folder+stream+'.bin')
            need(dict(size=len(data),sha256=hashlib.sha256(data).hexdigest()) == stage[stream], 'raw stream missing/mutated')
        for path,value in stage.get('reports',{}).items():
            data = read(path)
            need(dict(size=len(data),sha256=hashlib.sha256(data).hexdigest()) == value, 'result report missing/mutated')
        for p,value in stage['binaries_before'].items():
            need(stage['binaries_after'].get(p) == value, 'stage binary changed')
        for p,value in stage['binaries_after'].items():
            need(binary_pins.get(p) == value, 'swapped binary identity')
    if full_contract:
        validate_semantics(read,expected,result)
        if expected['job_key']!='linux-sanitizers':
            for mode in ('normal','optimized'):
                name='mcp_directory_search-'+mode
                report=json.loads(read('reports/'+name+'/RESULT.json'))
                need(report.get('schema')=='qbrain-n49d-mcp-directory-process-v1' and report.get('passed') is True and
                     report.get('status')=='passed' and report.get('python_optimized')==(mode=='optimized'), 'MCP process report incomplete')
                need(report.get('stdio')==dict(status='passed',profiles=['full','memory']), 'stdio profiles missing')
                prefix='reports/'+name+'/'
                def raw_descriptor(value):
                    path=value.get('path','')
                    need(path.startswith('raw/') and all(p not in ('','.','..') for p in path.split('/')), 'MCP raw path invalid')
                    data=read(prefix+path)
                    need(len(data)==value.get('bytes') and hashlib.sha256(data).hexdigest()==value.get('sha256'), 'MCP raw evidence mismatch')
                    return data
                need(report.get('commands') and report.get('command_count')==len(report['commands']), 'MCP command inventory incomplete')
                process_stage=json.loads(read('stages/'+name+'/result.json'))
                production=process_stage['argv'][process_stage['argv'].index('--binary')+1]
                for command in report['commands']:
                    need(command.get('argv') and command['argv'][0]==production, 'MCP command binary path mismatch')
                    need(command.get('status') in ('completed','server_stopped_after_checks') and
                         command.get('finalization_classification')!='timeout', 'MCP command finalization incomplete')
                    ownership=command.get('ownership',{})
                    need(command.get('stable') is True and ownership.get('stable') is True and ownership.get('cleanup_ok') is True and
                         ownership.get('readers_done') is True and ownership.get('classification') in ('passed','stopped'), 'MCP process ownership incomplete')
                    need(command.get('exit')==ownership.get('exit'), 'MCP command exit mismatch')
                    for key in ('stdin','stdout','stderr'):
                        raw_descriptor(command[key])
                        if key!='stdin':need(ownership.get(key)==dict(size=command[key]['bytes'],sha256=command[key]['sha256']), 'MCP stable stream binding mismatch')
                exchanges=report.get('exchanges',[])
                need(report.get('exchange_count')==len(exchanges), 'MCP exchange inventory mismatch')
                for exchange in exchanges:
                    need(exchange.get('status')=='completed', 'MCP exchange incomplete')
                    raw_descriptor(exchange['request']);raw_descriptor(exchange['response'])
                provider=report.get('provider_http',{})
                if expected['job_key'].startswith('windows'):
                    batches=provider.get('batches',[]);requests=provider.get('requests',[])
                    need(provider.get('required') is True and provider.get('status')=='passed' and
                         provider.get('profiles')==['full','memory'] and provider.get('transports')==['stdio','http'] and
                         {(b['profile'],b['transport']) for b in batches}=={(p,t) for p in ('full','memory') for t in ('stdio','http')} and len(batches)==4,
                         'native provider fixture missing')
                    negatives=[];positives=[]
                    for batch in batches:
                        need(batch.get('status')=='passed' and batch.get('negative_request_count')==0 and batch.get('negative_query_count')==27 and
                             len(batch.get('negative_cases',[]))==27 and len(batch.get('positive_controls',[]))==2,'provider batch incomplete')
                        need(all(c.get('provider_requests')==0 and c.get('expected_error') for c in batch['negative_cases']), 'provider rejection made request')
                        negatives.extend(c['query'] for c in batch['negative_cases']);positives.extend(batch['positive_controls'])
                    need(len(set(negatives))==108 and provider.get('negative_query_count')==108 and provider.get('negative_request_count')==0 and
                         provider.get('positive_request_count')==8 and len(requests)==len(positives)==8,'provider aggregate counts')
                    need(len({p['query'] for p in positives})==8,'provider positive queries not fresh')
                    for index,(positive,capture) in enumerate(zip(positives,requests)):
                        need(positive.get('record_index')==index and positive.get('provider_requests')==1 and positive['query']==capture.get('query') and
                             capture.get('status')=='completed' and positive['query'] not in negatives,'provider positive capture binding')
                        request_raw=raw_descriptor(capture['request']);response_raw=raw_descriptor(capture['response'])
                        need(json.loads(request_raw.split(b'\r\n\r\n',1)[1]).get('input')==[positive['query']] and
                             response_raw.startswith(b'HTTP/1.1 200 '),'provider wire capture mismatch')
                else:
                    need(provider.get('required') is False and provider.get('status')=='not_applicable' and
                         not any(k in provider for k in ('requests','batches','positive_request_count','negative_request_count')), 'Linux provider-network claim')
                http=report.get('http',{})
                if expected['job_key'].startswith('windows'):
                    need(http.get('required') is True and http.get('status')=='passed' and
                         http.get('profiles')==['full','memory'] and bool(http.get('authentication')), 'native authenticated HTTP missing')
                else:
                    need(http.get('required') is False and http.get('status')=='not_applicable' and 'profiles' not in http,
                         'Linux HTTP cannot claim native acceptance')
                stage=json.loads(read('stages/'+name+'/result.json'))
                need(report['binary_sha256'] in {v['sha256'] for v in stage['binaries_before'].values()}, 'MCP tested binary mismatch')
        before=read('reports/source-before.json'); after=read('reports/source-after.json')
        need(before==after and dict(size=len(before),sha256=hashlib.sha256(before).hexdigest())==result['source_before'],
             'source report changed after capture')
        binding=json.loads(before)
        need(binding.get('passed') is True and binding.get('commit')==expected['commit'] and
             binding.get('tree')==expected['tree'] and binding.get('base')==source_guard.BASE and
             binding.get('base_tree')==source_guard.BASE_TREE and binding.get('precommit') is False and
             binding.get('parent')==source_guard.CORRECTION_PARENT and
             binding.get('parent_tree')==source_guard.CORRECTION_PARENT_TREE and
             binding.get('correction_changed')==sorted(source_guard.CORRECTION_PATHS),
             'source/candidate binding mismatch')
        need(json.loads(read('source/dependencies.json'))==binding['dependency_sha256'], 'dependency manifest mismatch')
        inventory=read('source/tree-inventory.bin')
        need(hashlib.sha256(inventory).hexdigest()==binding['inventory_sha256'], 'tree inventory identity mismatch')
        tree=source_guard.generic_tree_reader(ROOT)(inventory,expected['tree'])
        approved=sorted(source_guard.ALLOW)
        need(binding.get('changed')==approved,'fixed changed source list mismatch')
        changed=binding.get('changed_files')
        need(isinstance(changed,dict) and sorted(changed)==approved,'fixed changed source map mismatch')
        changed_source_members(files)
        for path in approved:
            row=changed[path]
            data=read('source/changed/'+path)
            need(row['mode']=='100644' and hashlib.sha256(data).hexdigest()==row['sha256'] and source_guard.blob(data)==row['blob'] and
                 tree.get(path)==(row['mode'],row['blob']), 'changed source bytes mismatch')
        retained=result['retained_binaries']
        expected_names=set(TARGETS[:2]) if expected['job_key']=='linux-sanitizers' else {'qbrain.exe' if expected['job_key'].startswith('windows') else 'qbrain'}
        need({Path(row['path']).name for row in retained.values()}==expected_names and len(retained)==len(expected_names), 'required binary bytes missing')
        for original,row in retained.items():
            need(row['path'].startswith('binaries/'), 'binary member location')
            value={k:row[k] for k in ('size','sha256')}
            need(binary_pins.get(original)==value, 'retained binary identity swapped')
            if hasattr(read,'describe'):
                observed=read.describe(row['path'])
            else:
                data=read(row['path']); observed=dict(size=len(data),sha256=hashlib.sha256(data).hexdigest())
            need(observed==value, 'retained binary bytes mutated')
    return result


def evidence_inventory(root, limits=LIMITS):
    paths=[]; size=0
    for p in sorted(Path(root).rglob('*')):
        need(not p.is_symlink(), 'evidence symlink')
        if p.is_dir(): continue
        need(p.is_file(), 'evidence nonregular member')
        size += p.stat().st_size; paths.append(p)
        need(size <= limits['raw'] and len(paths) <= limits['members'], 'raw/member cap exceeded')
    need(paths, 'empty evidence')
    return dict(raw_bytes=size,member_count=len(paths))


def validate_manifest(raw, identity, limits=LIMITS):
    need(0 < len(raw) <= limits['manifest'], 'N49D manifest cap')
    m=json.loads(raw); same_identity(m['identity'],identity)
    need(m['schema']=='qbrain-n49c-evidence-parts-v1','transport schema mismatch')
    rows=m['files']; need(isinstance(rows,list) and 0<len(rows)<=limits['members'],'N49D member cap')
    names=[r['path'] for r in rows]
    need(names==sorted(set(names)),'duplicate/unsorted evidence members')
    for row in rows:
        name=row['path']
        need(isinstance(name,str) and name and '\\' not in name and ':' not in name and
             all(p not in ('','.','..') for p in name.split('/')),'unsafe member')
        need(isinstance(row['size'],int) and 0<=row['size']<=limits['raw'] and stat.S_ISREG(row['mode']), 'member type/size')
        need(re.fullmatch('[0-9a-f]{64}',row['sha256']) is not None,'invalid leaf digest')
    need(sum(r['size'] for r in rows)==m['uncompressed_bytes']<=limits['raw'],'N49D raw cap')
    need(0<m['archive']['size']<=limits['compressed'],'N49D compressed cap')
    need(len(m['parts'])==1,'exactly one part00 required')
    part=m['parts'][0]
    need(part==dict(index=0,file='evidence.part',size=m['archive']['size'],sha256=m['archive']['sha256']), 'single part binding mismatch')
    return m


def package(root, staging, identity, limits=LIMITS, *, _generic_packager=None):
    before=evidence_inventory(root,limits)
    snapshots={p.relative_to(root).as_posix():descriptor(p) for p in Path(root).rglob('*') if p.is_file()}
    def read(p):return (Path(root)/p).read_bytes()
    read.describe=lambda p:descriptor(Path(root)/p)
    validate_recordings(read,identity,files=snapshots)
    # Keep every original inherited packager guard. CI has its required capacity.
    invoke=_generic_packager if _generic_packager is not None else generic_archive()['package_evidence']
    result=invoke(root,staging,identity)
    need(result.get('passed') is True and result.get('identity')==identity,'generic package result identity/status')
    manifest=Path(result['parts_root'])/'00'/'manifest.json'
    raw=manifest.read_bytes();m=validate_manifest(raw,identity,limits)
    need(result.get('manifest_sha256')==hashlib.sha256(raw).hexdigest() and result.get('manifest_bytes')==len(raw) and
         result.get('archive_sha256')==m['archive']['sha256'],'generic package result digest mismatch')
    part=manifest.parent/'evidence.part'
    need(descriptor(part)==m['archive'],'generic package part mismatch')
    need({r['path']:{k:r[k] for k in ('size','sha256')} for r in m['files']}==snapshots,'generic package leaf inventory mismatch')
    generic_archive()['verify_evidence_archive'](part,m)
    need({p.relative_to(root).as_posix():descriptor(p) for p in Path(root).rglob('*') if p.is_file()}==snapshots,'evidence mutated during package')
    need(evidence_inventory(root,limits)==before,'evidence changed during package')
    need(result['part_count']==1 and result['archive_size']==m['archive']['size'],'package part mismatch')
    result.update(before)
    result['required_binary_bytes']={p.name:p.stat().st_size for p in (Path(root)/'binaries').iterdir()}
    result['outer_zip_upper_bound']=result['archive_size']+result['manifest_bytes']+4096
    need(result['outer_zip_upper_bound']<=limits['outer'],'outer ZIP framing cap')
    return result


def staging_size(root):
    total=0
    for p in Path(root).rglob('*'):
        need(not p.is_symlink(),'review staging symlink')
        if p.is_file(): total+=p.stat().st_size
    return total


def review_text_bytes(root):
    # Only top-level downloaded ZIPs are download storage, everything else is
    # retained review material. This includes prior consumption reports.
    root=Path(root)
    return sum(p.stat().st_size for p in root.rglob('*') if p.is_file() and
               not (p.parent==root and p.suffix.lower()=='.zip'))


def review_selection(result, files):
    """Explicit text subset; every leaf and required report is validated first.

    Keep source identity/changed bytes, stage command/exit records, required
    reports (source-after is an already-verified duplicate), and raw output for
    selftests, CTest, canonical/native, sanitizer, and report-less legacy drivers.
    Other exact raw bytes remain in the retained, independently verified ZIP.
    """
    specs=stage_contract(result['identity'],result['locations'])
    names={'qualification.json','source/tree-inventory.bin','source/dependencies.json'}
    names.update(changed_source_members(r['path'] for r in files))
    for name,spec in specs.items():
        names.add('stages/'+name+'/result.json')
        names.update(p for p in spec['reports'] if p!='reports/source-after.json')
        if (name.startswith(('selftest-','sanitize-','hooks-','memory_cycle-')) or
                name in ('ctest-run','canonical-run','canonical-groups','direct-tests')):
            names.update('stages/'+name+'/'+stream+'.bin' for stream in ('stdout','stderr'))
    by_name={r['path']:r for r in files}
    need(names<=set(by_name),'required review selection missing')
    need(not any(n.startswith('binaries/') for n in names),'binary extraction prohibited')
    return [by_name[name] for name in sorted(names)]


def consume(outer, review_root, identity, manifest_sha256, artifact_sha256, limits=LIMITS):
    """Input must be the file from the supported GitHub download_file route."""
    outer=Path(outer); review_root=Path(review_root)
    same_identity(identity,identity)
    need(outer.is_file() and not outer.is_symlink() and 0<outer.stat().st_size<=limits['outer'], 'outer ZIP cap/type')
    need(digest(outer)==artifact_sha256.removeprefix('sha256:'),'independent GitHub artifact digest mismatch')
    review_root.mkdir(parents=True,exist_ok=True)
    need(outer.resolve().is_relative_to(review_root.resolve()), 'download must reside in aggregate review staging')
    retained_text=review_text_bytes(review_root)
    need(retained_text<=limits['text'],'aggregate retained-text cap')
    need(staging_size(review_root)+limits['compressed']+limits['text']-retained_text<=limits['staging'],'consumer staging cap')
    need(shutil.disk_usage(review_root).free>=limits['reserve']+limits['compressed']+limits['text'],'consumer reserve')
    with zipfile.ZipFile(outer) as z:
        need(sorted(z.namelist())==['evidence.part','manifest.json'],'missing/extra outer member')
        for info in z.infolist():
            mode=info.external_attr>>16
            need(not info.is_dir() and (not stat.S_IFMT(mode) or stat.S_ISREG(mode)) and not info.flag_bits&1,'unsafe outer member')
        info=z.getinfo('manifest.json'); need(0<info.file_size<=limits['manifest'],'outer manifest cap')
        raw=z.read(info); need(hashlib.sha256(raw).hexdigest()==manifest_sha256,'independent manifest digest mismatch')
        m=validate_manifest(raw,identity,limits)
        info=z.getinfo('evidence.part'); need(info.file_size==m['archive']['size'],'outer part size')
        with tempfile.TemporaryDirectory(prefix='n49d-review-',dir=review_root) as tmp:
            archive=Path(tmp)/'evidence.zip'; h=hashlib.sha256(); count=0
            with z.open(info) as src, archive.open('wb') as dst:
                while data:=src.read(MIB):
                    count+=len(data);need(count<=limits['compressed'],'part expansion cap');h.update(data);dst.write(data)
            need(count==m['archive']['size'] and h.hexdigest()==m['archive']['sha256'],'wrong part digest')
            generic_archive()['verify_evidence_archive'](archive,m)
            with zipfile.ZipFile(archive) as leaves:
                def read(name):
                    need(leaves.getinfo(name).file_size<=limits['text'],'review record cap')
                    return leaves.read(name)
                # The unchanged archive validator already streamed every member.
                leaf_descriptors={r['path']:{k:r[k] for k in ('size','sha256')} for r in m['files']}
                read.describe=lambda name:leaf_descriptors[name]
                result=validate_recordings(read,identity,files=[r['path'] for r in m['files']])
                selected=review_selection(result,m['files'])
                receipt=dict(passed=True,identity=identity,artifact_sha256=artifact_sha256,
                    manifest_sha256=manifest_sha256,archive_sha256=m['archive']['sha256'],
                    selected_review_members=[r['path'] for r in selected],all_archive_leaves_stream_verified=True,
                    all_required_semantic_reports_verified=True,binary_members=[r for r in m['files'] if r['path'].startswith('binaries/')])
                receipt_raw=(json.dumps(receipt,sort_keys=True,indent=2)+'\n').encode('utf-8')
                need(retained_text+sum(r['size'] for r in selected)+len(receipt_raw)<=limits['text'],'aggregate retained-text cap')
                target=review_root/(identity['job_key']+'-'+identity['run_id']+'-'+identity['run_attempt'])
                need(not target.exists(),'review destination exists');target.mkdir()
                for row in selected:
                    dest=target/row['path'];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(read(row['path']))
                (target/'consumption.json').write_bytes(receipt_raw)
    need(staging_size(review_root)<=limits['staging'] and review_text_bytes(review_root)<=limits['text'],'consumer final aggregate cap')
    return result


def native_groups(registry, output):
    path=ROOT/'.ci/validate_native_log.py'
    source_guard.checkout_bytes(path.read_bytes(),'352de0d8df857e2fb5b2e8a5783d49874d585447',os.name=='nt')
    ns={'re':re,'Counter':__import__('collections').Counter}
    nodes=[n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='verified_groups']
    need(len(nodes)==1,'native parser primitive missing')
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
    return ns['verified_groups'](registry,output,expected_count=60)


def verify_native(registry, output):
    return native_groups(Path(registry).read_text(encoding='utf-8'),Path(output).read_text(encoding='utf-8',errors='replace'))


def ctest_values(value, junit):
    names=[t['name'] for t in value['tests']]
    need(sorted(names)==sorted(TESTS) and len(names)==len(set(names)), 'selected CTest inventory mismatch')
    root=ET.fromstring(junit); cases=root.findall('.//testcase')
    need(sorted(t.attrib['name'] for t in cases)==sorted(TESTS),'actual CTest set mismatch')
    need(all(not list(t.findall('skipped')+t.findall('failure')+t.findall('error')) and
             t.attrib.get('status','run') not in ('notrun','disabled') for t in cases),'CTest skip/failure')
    return names


def verify_ctest(inventory, junit):
    return ctest_values(json.loads(Path(inventory).read_text(encoding='utf-8')),Path(junit).read_bytes())


def validate_sanitizer_flags(effective):
    import shlex
    need(effective.get('passed') is True and effective.get('compile_commands'),'sanitizer report incomplete')
    for row in effective['compile_commands']:
        args=row.get('arguments') or shlex.split(row['command'])
        need(not any(re.search(r'(^|[-/])D\s*NDEBUG(?:=|$)',a) or (a in ('-D','/D') and i+1<len(args) and re.match(r'NDEBUG(?:=|$)',args[i+1])) for i,a in enumerate(args)), 'NDEBUG in effective compilation')
        need('-fsanitize=address,undefined' in args and '-fno-omit-frame-pointer' in args and
             [a for a in args if re.fullmatch(r'-g.*',a)][-1:]==['-g0'] and
             [a for a in args if re.fullmatch(r'-O.*',a)][-1:]==['-O1'],'effective sanitizer flags missing')
    need(set(effective['link_commands'])==set(TARGETS[:2]) and all('-fsanitize=address,undefined' in c for c in effective['link_commands'].values()),'sanitizer link flags missing')
    need(effective['runtime_options']==dict(ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1'),'sanitizer runtime options missing')


def verify_sanitizer(build, output):
    import shlex
    rows=json.loads((build/'compile_commands.json').read_text(encoding='utf-8'))
    need(rows,'compile command inventory missing')
    selected=[]
    for row in rows:
        if any(t in row.get('command','') or t in row.get('output','') for t in TARGETS[2:]):
            continue
        args=row.get('arguments') or shlex.split(row['command'])
        need(not any(re.search(r'(^|[-/])D\s*NDEBUG(?:=|$)',a) or
                     (a in ('-D','/D') and i+1<len(args) and re.match(r'NDEBUG(?:=|$)',args[i+1]))
                     for i,a in enumerate(args)),'NDEBUG in effective compilation')
        need('-fsanitize=address,undefined' in args and '-fno-omit-frame-pointer' in args,'missing sanitizer instrumentation')
        need([a for a in args if re.fullmatch(r'-g.*',a)][-1:]==['-g0'],'effective debug symbols enabled')
        need([a for a in args if re.fullmatch(r'-O.*',a)][-1:]==['-O1'],'effective sanitizer optimization mismatch')
        selected.append(row)
    links={t:(build/'CMakeFiles'/(t+'.dir')/'link.txt').read_text(encoding='utf-8') for t in TARGETS[:2]}
    need(all('-fsanitize=address,undefined' in text for text in links.values()),'sanitizer link flags missing')
    dump(output,dict(passed=True,compile_commands=selected,link_commands=links,
        runtime_options=dict(ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')))


def run_job(args):
    source=args.source.resolve(strict=True); build=args.build.absolute(); output=args.output.absolute()
    need(source==ROOT,'qualification must use its own candidate source')
    need(args.job in JOBS and (os.name=='nt')==args.job.startswith('windows'),'job/platform mismatch')
    need(not output.exists() and not build.exists(),'fresh build/evidence directories required')
    need(source not in output.parents and source not in build.parents,'CMake build and evidence must be outside source')
    if args.job=='windows-msvc': need(not (source/'build/cl').exists(),'fresh direct-MSVC output required')
    identity=dict(commit=args.commit,tree=args.tree,run_id=args.run_id,run_attempt=args.run_attempt,job_key=args.job,job_label=args.job)
    same_identity(identity,identity)
    env={k:v for k,v in os.environ.items() if not BLOCKED.search(k)}
    env['PYTHONDONTWRITEBYTECODE']='1'
    env['PYTHONIOENCODING']='utf-8'
    if args.job=='linux-sanitizers':
        env.update(ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    recorder=Recorder(output,identity,required_stages(args.job),env,source)
    recorder.locations=dict(source=str(source),build=str(build),output=str(output),python=sys.executable)
    contracts=stage_contract(identity,recorder.locations)
    (output/'reports').mkdir();(output/'source').mkdir();(output/'binaries').mkdir()
    python=[sys.executable]; guard=source/'.ci/check_n49d_sources.py'
    source_reports=[output/'reports/source-before.json',output/'reports/source-after.json']
    guard_command=lambda report:python+[str(guard),'--source',str(source),'--commit',args.commit,'--tree',args.tree,'--report',str(report)]
    def stage(name,argv,timeout=600,**kw):
        spec=contracts[name]
        need(list(map(str,argv))==spec['argv'] and timeout==spec['timeout_seconds'] and
             [Path(p).relative_to(output).as_posix() for p in kw.get('reports',())]==spec['reports'], 'runner fixed contract drift')
        return recorder.run(name,argv,timeout,**kw)
    try:
        stage('source-before',guard_command(source_reports[0]),120,reports=[source_reports[0]])
        pre=json.loads(source_reports[0].read_text(encoding='utf-8'))
        (output/'source/tree-inventory.bin').write_bytes(source_guard.git(source,'ls-tree','-r','--full-tree','-z',args.commit))
        dump(output/'source/dependencies.json',pre['dependency_sha256'])
        for path in pre['changed']:
            dest=output/'source/changed'/path;dest.parent.mkdir(parents=True,exist_ok=True)
            # Preserve canonical candidate bytes; checkout may be verified CRLF.
            dest.write_bytes(source_guard.git(source,'show',args.commit+':'+path))
        for mode in ('normal','optimized'):
            stage('selftest-'+mode,python+(['-O'] if mode=='optimized' else [])+[str(source/'.ci/test_n49d_source_contract.py')],120)
        selected=[]; production=None
        if args.job=='windows-msvc':
            production=source/'build/cl/qbrain.exe'; canonical=source/'build/cl/qbrain_tests.exe'
            stage('direct-production',['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File','scripts/build-cl.ps1'],1800,produced=[production])
            stage('direct-tests',['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File','scripts/build-tests-cl.ps1','-SkipProductionBuild'],1800,binaries=[production],produced=[canonical])
            stage('canonical-groups',python+[str(__file__),'verify-native','--registry',str(source/'tests/test_main.cpp'),'--log',str(output/'stages/direct-tests/stdout.bin')],120,binaries=[production,canonical])
        else:
            configure=['cmake','-S',str(source),'-B',str(build),'-DQBRAIN_WITH_PG=OFF',
                       '-DCMAKE_PROJECT_qbrain_INCLUDE='+str(source/'.ci/mcp_directory_search_targets.cmake'),'-DCMAKE_BUILD_TYPE=Debug']
            targets=['qbrain',*TARGETS]
            if args.job=='linux-sanitizers':
                configure += ['-DCMAKE_C_COMPILER=clang','-DCMAKE_CXX_COMPILER=clang++','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
                    '-DCMAKE_C_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer',
                    '-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer',
                    '-DCMAKE_C_FLAGS_DEBUG=-O1 -g0','-DCMAKE_CXX_FLAGS_DEBUG=-O1 -g0',
                    '-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined']
                targets=list(TARGETS[:2])
            elif args.job=='linux-cmake':
                configure += ['-DCMAKE_CXX_FLAGS_DEBUG=-O0 -g0','-DCMAKE_C_FLAGS_DEBUG=-O0 -g0']
            stage('configure',configure,180)
            exe=lambda target:build/('Debug' if os.name=='nt' else '')/(target+('.exe' if os.name=='nt' else ''))
            selected=[exe(target) for target in targets]
            stage('build',['cmake','--build',str(build),'--config','Debug','--target',*targets,'--parallel','2'],1800,produced=selected)
            if args.job=='linux-sanitizers':
                effective=output/'reports/sanitizer-effective.json'
                stage('sanitizer-flags',python+[str(__file__),'verify-sanitizer','--build',str(build),'--report',str(effective)],120,binaries=selected,reports=[effective])
                for name,binary in zip(('sanitize-mcp','sanitize-directory'),selected):
                    stage(name,[str(binary)],binaries=selected,
                          check=lambda name=name:need((output/'stages'/name/'stderr.bin').stat().st_size==0,'sanitizer stderr nonempty'))
            else:
                production=exe('qbrain'); regex='^('+'|'.join(TESTS)+')$'
                stage('ctest-inventory',['ctest','--test-dir',str(build),'-C','Debug','-R',regex,'--show-only=json-v1'],120,binaries=selected)
                inventory=output/'stages/ctest-inventory/stdout.bin'
                need(sorted(t['name'] for t in json.loads(inventory.read_text())['tests'])==sorted(TESTS),'CTest inventory must match before run')
                junit=output/'reports/ctest.xml'
                stage('ctest-run',['ctest','--test-dir',str(build),'-C','Debug','-R',regex,'--output-on-failure','--output-junit',str(junit)],600,binaries=selected,reports=[junit])
                stage('ctest-completeness',python+[str(__file__),'verify-ctest','--inventory',str(inventory),'--junit',str(junit)],120,binaries=selected)
                if args.job=='windows-cmake':
                    canonical=exe('qbrain_tests');probe=exe('qbrain_http_probe')
                    stage('canonical-build',['cmake','--build',str(build),'--config','Debug','--target','qbrain_tests','qbrain_http_probe','--parallel','2'],1800,binaries=selected,produced=[canonical,probe])
                    stage('canonical-run',[str(canonical)],binaries=[canonical,production])
                    stage('canonical-groups',python+[str(__file__),'verify-native','--registry',str(source/'tests/test_main.cpp'),'--log',str(output/'stages/canonical-run/stdout.bin')],120,binaries=[canonical,production])
        if production:
            for mode in ('normal','optimized'):
                prefix=python+(['-O'] if mode=='optimized' else [])
                for driver in DRIVERS:
                    name=driver+'-'+mode; command=prefix+[str(source/'.ci'/('test_'+driver+'.py')),'--binary',str(production)]
                    reports=[]
                    if driver in ('mcp_directory_search','directory_search'):
                        destination=output/'reports'/name;command+=['--output',str(destination)];reports=[destination/'RESULT.json']
                    elif driver in ('context_process','named_arguments'):
                        destination=output/'reports'/(name+'.json');command+=['--report',str(destination)];reports=[destination]
                    stage(name,command,binaries=[production],reports=reports)
                if args.job=='windows-cmake':
                    report=output/'reports'/('winhttp-'+mode+'.json')
                    stage('winhttp-'+mode,prefix+[str(source/'.ci/test_http_transport.py'),'--probe',str(probe),'--report',str(report)],binaries=[production,probe],reports=[report])
        stage('source-after',guard_command(source_reports[1]),120,reports=[source_reports[1]],binaries=list(map(Path,recorder.binary_pins)))
        retained=[production] if production else selected
        for p in retained:
            need(descriptor(p)==recorder.binary_pins[str(p)],'tested binary changed before retention')
            shutil.copyfile(p,output/'binaries'/p.name)
        result=recorder.finish(descriptor(source_reports[0]),descriptor(source_reports[1]))
        result['retained_binaries']={str(p):dict(path='binaries/'+p.name,**descriptor(output/'binaries'/p.name)) for p in retained}
        dump(output/'qualification.json',result)
        def read(p):return (output/p).read_bytes()
        read.describe=lambda p:descriptor(output/p)
        validate_recordings(read,identity,files=[p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()])
        package_result=package(output,args.package,identity)
        dump(args.package/'PACKAGE.json',package_result)
        print(json.dumps(package_result,sort_keys=True))
        return 0
    except Exception as e:
        dump(output/'failure.json',dict(passed=False,identity=identity,error=str(e),stages=recorder.stages))
        diagnostics=args.package.parent/'n49d-diagnostics'; diagnostics.mkdir(parents=True,exist_ok=True)
        failure_diagnostics(output,diagnostics/'failure.json',identity,recorder.stages,recorder.required,e)
        print(str(e),file=sys.stderr)
        return 1


def failure_diagnostics(root, destination, identity, stages, required, error):
    """Retain exact bounded bytes, identifying every truncation as partial failure."""
    root=Path(root); files={}
    if stages:
        last=root/'stages'/stages[-1]
        for name,cap in (('stdout.bin',64*1024),('stderr.bin',64*1024),('result.json',16*1024)):
            path=last/name
            if not path.is_file():continue
            full=descriptor(path)
            with path.open('rb') as stream:
                offset=max(0,full['size']-cap); stream.seek(offset); raw=stream.read(cap)
            files[path.relative_to(root).as_posix()]=dict(**full,retained_offset=offset,retained_bytes=len(raw),
                truncated=offset!=0,encoding='base64',data=base64.b64encode(raw).decode('ascii'))
        report_path=last/'result.json'
        if report_path.is_file():
            report=json.loads(report_path.read_text(encoding='utf-8'))
            for name in report.get('requested_reports',[])[:2]:
                path=root/name
                if not path.is_file():continue
                full=descriptor(path)
                with path.open('rb') as stream:
                    offset=max(0,full['size']-8*1024);stream.seek(offset);raw=stream.read(8*1024)
                files[name]=dict(**full,retained_offset=offset,retained_bytes=len(raw),truncated=offset!=0,
                    encoding='base64',data=base64.b64encode(raw).decode('ascii'))
    payload=dict(passed=False,status='failed-partial-diagnostics',identity=identity,error=str(error),
                 stages=stages,required=required,files=files)
    raw=json.dumps(payload,sort_keys=True,indent=2).encode('utf-8')
    need(len(raw)<=256*1024,'diagnostics cap')
    Path(destination).parent.mkdir(parents=True,exist_ok=True);Path(destination).write_bytes(raw)
    return payload


def main(argv=None):
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='action',required=True)
    q=sub.add_parser('run');q.add_argument('--source',type=Path,default=ROOT)
    q.add_argument('--job',choices=JOBS,required=True);q.add_argument('--build',type=Path,required=True)
    q.add_argument('--output',type=Path,required=True);q.add_argument('--package',type=Path,required=True)
    for name in ('commit','tree','run-id','run-attempt'):q.add_argument('--'+name,required=True)
    q=sub.add_parser('consume');q.add_argument('--outer',type=Path,required=True);q.add_argument('--review-root',type=Path,required=True)
    q.add_argument('--identity',type=Path,required=True);q.add_argument('--manifest-sha256',required=True);q.add_argument('--artifact-sha256',required=True)
    q=sub.add_parser('verify-native');q.add_argument('--registry',type=Path,required=True);q.add_argument('--log',type=Path,required=True)
    q=sub.add_parser('verify-ctest');q.add_argument('--inventory',type=Path,required=True);q.add_argument('--junit',type=Path,required=True)
    q=sub.add_parser('verify-sanitizer');q.add_argument('--build',type=Path,required=True);q.add_argument('--report',type=Path,required=True)
    args=p.parse_args(argv)
    try:
        if args.action=='run':return run_job(args)
        if args.action=='consume':consume(args.outer,args.review_root,json.loads(args.identity.read_text()),args.manifest_sha256,args.artifact_sha256)
        elif args.action=='verify-native':print(json.dumps(verify_native(args.registry,args.log)))
        elif args.action=='verify-ctest':print(json.dumps(verify_ctest(args.inventory,args.junit)))
        elif args.action=='verify-sanitizer':verify_sanitizer(args.build,args.report)
        return 0
    except Exception as e:
        print(str(e),file=sys.stderr);return 1


if __name__=='__main__':sys.exit(main())
