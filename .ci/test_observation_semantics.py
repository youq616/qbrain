"""Independent real subprocess checks of dispatch versus final process/output state.
No signal handler/ignore/preexec monkeypatch. Closed pipe exists before child exec.
Only synthetic temporary HOME and numeric-loopback HTTP data. No PG or paid accounts.
"""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import hashlib
import json
import os
import signal
import subprocess
import tempfile
import threading


def encode(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def main(binary, semantics_binary, output):
    binary = binary.resolve(strict=True)
    semantics_binary = semantics_binary.resolve(strict=True)
    output.mkdir(parents=True, exist_ok=False)
    (output/'raw').mkdir()
    checks, commands, wire_requests = [], [], []
    def need(ok, label):
        checks.append(dict(name=label, passed=bool(ok)))
        if not ok:
            raise ValueError(label)
    env0 = {k:v for k,v in os.environ.items() if not k.upper().startswith(
        ('QBRAIN', 'PG', 'OPENAI', 'ANTHROPIC', 'GH_TOKEN', 'GITHUB_TOKEN'))}
    forbidden = [b'PRIVATE_ERROR_SENTINEL', b'PRIVATE_MODEL_SENTINEL', b'PRIVATE_PROMPT_SENTINEL',
                 b'PRIVATE_KEY_SENTINEL', b'PRIVATE_REPLY_SENTINEL', b'PRIVATE_DISPATCH_EXCEPTION']
    def record(label, args, home, env, closed=False):
        if closed:
            reader, writer = os.pipe()
            os.close(reader)  # No reader before process creation: deterministic, not a timing race.
            try:
                proc = subprocess.Popen(list(map(str,args)), stdin=subprocess.DEVNULL,
                    stdout=writer, stderr=subprocess.PIPE, cwd=home, env=env, restore_signals=True)
            finally:
                os.close(writer)
            try:
                _, stderr = proc.communicate(timeout=40)
            except BaseException:
                proc.kill();proc.communicate();raise
            stdout = b''
            code = proc.returncode
        else:
            proc = subprocess.run(list(map(str,args)), input=b'', capture_output=True,
                                  cwd=home, env=env, timeout=40, restore_signals=True)
            stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
        idx = len(commands)
        (output/'raw'/f'{idx:03d}.stdout').write_bytes(stdout)
        (output/'raw'/f'{idx:03d}.stderr').write_bytes(stderr)
        commands.append(dict(label=label, closed_reader=closed, parent_observed_exit=code,
            stdout_captured=not closed, stdout_sha256=hashlib.sha256(stdout).hexdigest(),
            stderr_sha256=hashlib.sha256(stderr).hexdigest()))
        return code, stdout, stderr
    def inspect(folder, dispatch_state='returned', dispatch_return=0):
        r = json.loads((folder/'report.json').read_bytes())
        need(r['schema']=='qbrain-runtime-observation-v2' and 'command_exit' not in r,
             'v2 separates dispatch from process exit')
        need(r['dispatch_state']==dispatch_state and r['dispatch_return']==dispatch_return,
             'dispatch result or exception observed explicitly')
        need(all(r[k] is None for k in ('process_exit','stdout_complete','stderr_complete')),
             'self-report cannot certify final process or output completion')
        need(r['completion_scope']=='http_attempt_records_only' and r['recording_complete'] is True,
             'retained HTTP completeness scope is explicit')
        for file in folder.rglob('*.json'):
            need(not any(s in file.read_bytes() for s in forbidden), 'no private error/content in sidecar')
        (output/(folder.name+'-report.json')).write_bytes(encode(r)+b'\n')
        return r
    try:
        with tempfile.TemporaryDirectory(prefix='n48w-p2-process-') as tmp:
            root = Path(tmp)
            def context(name):
                home=root/name;home.mkdir()
                env={**env0, 'HOME':str(home), 'USERPROFILE':str(home),
                     'LOCALAPPDATA':str(home), 'APPDATA':str(home)}
                return home, env
            # Open-output positive controls: original bytes and exit statuses unchanged.
            home,env=context('normal')
            plain=record('plain-help',[binary,'help'],home,env)
            observed=record('observed-help',[binary,'observe','--output',home/'help','--','help'],home,env)
            need(plain==observed and plain[0]==0, 'help stdout stderr and real exit unchanged')
            r=inspect(home/'help')
            bad=record('plain-command-error',[binary,'cost','report'],home,env)
            bad_observed=record('observed-command-error',[binary,'observe','--output',home/'error','--','cost','report'],home,env)
            need(bad==bad_observed and bad[0]!=0, 'ordinary command error behavior unchanged')
            inspect(home/'error',dispatch_return=bad[0])
            thrown=record('caught-dispatch-exception',[semantics_binary,'--throw',home/'throw'],home,env)
            need(thrown[0]==2 and b'observed_command_exception' in thrown[2] and not any(x in thrown[2] for x in forbidden),
                 'caught exception does not expose its private text')
            inspect(home/'throw','exception',None)
            # Parent sees completion only after wait; these values never mutate sidecar.
            rates=home/'rates.json';rates.write_bytes(encode(dict(schema='qbrain-observation-rates-v1',currency='USD',rates=[],assignments=[])))
            priced=record('price-open-output',[binary,'observe','cost','--report',home/'help/report.json','--assignments',rates],home,env)
            cost=json.loads(priced[1]);need(priced[0]==0 and cost['process_exit'] is None and cost['stdout_complete'] is None and
                cost['dispatch_return']==0 and cost['completion_scope']=='http_attempt_records_only', 'offline cost cannot upgrade output/process claim')
            for change in ('old_schema','command_exit','process_exit','stdout_complete','stderr_complete','dispatch_bool'):
                forged=dict(r)
                if change=='old_schema':forged['schema']='qbrain-runtime-observation-v1'
                elif change=='dispatch_bool':forged['dispatch_return']=False
                else:forged[change]=0 if change.endswith('exit') else True
                path=home/(change+'.json');path.write_bytes(encode(forged))
                result=record('reject-'+change,[binary,'observe','cost','--report',path,'--assignments',rates],home,env)
                need(result[0]==2,'false final-completion or old-schema claim rejected by real CLI')
            if os.name=='posix':
                for command in ('help','init'):
                    exits=[]
                    for observe in (False,True):
                        tag=('observed-' if observe else 'plain-')+command+'-closed'
                        home,env=context(tag)
                        args=['help'] if command=='help' else ['init','--no-default','--brain','p2-fixture']
                        if observe:args=['observe','--output',home/'closed','--',*args]
                        result=record(tag,[binary,*args],home,env,True);exits.append(result[0])
                        need(result[0]==-signal.SIGPIPE, 'inherited real SIGPIPE behavior retained, no ignore')
                        need(result[2]==b'','no new stdout-failure diagnostic from runtime')
                        if observe:
                            report=inspect(home/'closed')
                            need(report['dispatch_return']==0 and report['process_exit'] is None,
                                 'returned zero is not misreported as final process zero after SIGPIPE')
                            final=record('price-after-SIGPIPE',[binary,'observe','cost','--report',home/'closed/report.json',
                                '--assignments',rates],home,env)
                            need(final[0]==0 and json.loads(final[1])['process_exit'] is None,
                                 'pricing sealed HTTP records does not hide the unknown final process outcome')
                    need(exits[0]==exits[1], 'observed and ordinary signal outcome identical')
            else:
                # No POSIX signal assertion on Windows. Paired native closed-handle
                # executions still must retain the platform's ordinary behavior.
                for command in ('help','init'):
                    exits=[]
                    for observe in (False,True):
                        tag=('observed-' if observe else 'plain-')+command+'-closed'
                        home,env=context(tag)
                        args=['help'] if command=='help' else ['init','--no-default','--brain','p2-fixture']
                        if observe:args=['observe','--output',home/'closed','--',*args]
                        result=record(tag,[binary,*args],home,env,True);exits.append((result[0],result[2]))
                        if observe and (home/'closed/report.json').is_file():inspect(home/'closed')
                    need(exits[0]==exits[1], 'Windows closed handle behavior identical; no SIGPIPE claim')
            if os.name=='nt':
                statuses=['completed','cancelled','incomplete','failed','queued','in_progress','unexpected']
                class Handler(BaseHTTPRequestHandler):
                    def log_message(self,*_):pass
                    def do_POST(self):
                        n=int(self.headers.get('Content-Length','0'))
                        if not 0<n<65536:self.send_error(400);return
                        value=json.loads(self.rfile.read(n));state=value.get('fixture')
                        if self.path!='/responses' or state not in statuses:self.send_error(400);return
                        wire_requests.append(state)
                        data=encode(dict(object='response',status=state,error=dict(message='PRIVATE_ERROR_SENTINEL'),
                            model='PRIVATE_MODEL_SENTINEL',output_text='PRIVATE_REPLY_SENTINEL',usage=dict(input_tokens=10,output_tokens=2,total_tokens=12,
                            input_tokens_details=dict(cached_tokens=2,cache_write_tokens=1))))
                        self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
                server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
                worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
                home,env=context('wire')
                try:
                    call=record('wire-status-errors',[semantics_binary,'--wire',f'http://127.0.0.1:{server.server_port}',home/'envelopes'],home,env)
                    need(call[0]==0 and call[2]==b'' and wire_requests==statuses,'seven actual HTTP envelopes observed in order')
                finally:
                    server.shutdown();server.server_close();worker.join(timeout=5)
                wire=inspect(home/'envelopes')
                need(wire['counts']['started']==7 and wire['counts']['finished']==7,'all actual HTTP status envelopes retained')
                for state,row in zip(statuses,wire['records']):
                    expected='pending' if state in ('queued','in_progress') else 'unknown' if state=='unexpected' else state
                    need(row['usage']['provider_state']==expected and row['usage']['provider_error_present'] is True,
                         'actual HTTP explicit status and error coexist without overwrite')
                    need(row['usage']['provider_status_conflict']==(state=='completed'), 'actual contradictory completed envelope not success/failure inference')
                    need(row['usage']['state']==('unsupported' if expected in ('pending','unknown') else 'recognized'),
                         'actual HTTP pending/unknown plus error preserves f7 no-final-usage behavior')
        report=dict(schema='qbrain-observation-semantics-process-v1',passed=True,check_count=len(checks),checks=checks,
            commands=commands,command_count=len(commands),wire_statuses=wire_requests,posix_sigpipe_executed=os.name=='posix',
            platform=os.name,optimized=not __debug__,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
            semantics_binary_sha256=hashlib.sha256(semantics_binary.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            runtime_signal_behavior_changed=False,paid_provider_calls=0)
    except BaseException:
        (output/'PARTIAL.json').write_bytes(encode(dict(passed=False,checks=checks,commands=commands))+b'\n')
        raise
    (output/'RESULT.json').write_bytes(encode(report)+b'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('checks','commands')}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--semantics-binary',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();main(args.binary,args.semantics_binary,args.output)
