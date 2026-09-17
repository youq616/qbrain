"""Fail-closed N47K source-bound evidence. A checkpoint is not model consumption."""
from test_hook_diagnostic_process import EXPECTED_CHECKS, COMMAND_SCHEDULE, NEGATIVE

UNIT_SCENARIOS=('canonical records and exact session filtering', 'unknown and nested input fields cannot be echoed', 'required record values and numeric types remain exact', 'raw duplicate keys malformed UTF8 and depth are rejected', 'record byte cap cannot truncate a valid prefix', 'forgotten replay and failed phases never become consumption', 'inspection of empty config directory is read only', 'all five records retain fixed order and complete metadata', 'bad files are independent and never returned as raw bytes', 'direct API rejects ambiguous paths and invalid selection', 'config validation cannot select another host or follow database settings')

def require(ok,message):
    if not ok:raise ValueError(message)
def identity(r,source_commit,binary_sha256,script_sha256,native):
    require(isinstance(r,dict) and r.get('result')=='PASS','Hook diagnostic test failed')
    require(r.get('source_commit')==source_commit and r.get('tracked_tree_clean') is True,'wrong or dirty source')
    require(r.get('binary_sha256')==binary_sha256 and r.get('script_sha256')==script_sha256,'wrong binary or script')
    require(type(r.get('native_windows')) is bool and (not native or r['native_windows']),'native platform missing')
    require('error' not in r and 'error_type' not in r,'failure metadata present')
def validate_process(r,*,source_commit,binary_sha256,script_sha256,native=True):
    identity(r,source_commit,binary_sha256,script_sha256,native)
    cases=r.get('checks');require(isinstance(cases,list) and all(isinstance(c,dict) and c.get('status')=='PASS' for c in cases),'failed/missing checks')
    names=[c.get('name') for c in cases]
    require(len(names)==len(EXPECTED_CHECKS) and set(names)==EXPECTED_CHECKS,'wrong check set')
    require(type(r.get('check_count')) is int and r['check_count']==len(names),'wrong check count')
    counts=r.get('counts');require(isinstance(counts,dict) and set(counts)=={'total','pass','fail'} and all(type(x) is int for x in counts.values()) and counts=={'total':len(names),'pass':len(names),'fail':0},'bad summary')
    cmds=r.get('commands');require(isinstance(cmds,list) and len(cmds)==len(COMMAND_SCHEDULE) and all(isinstance(c,dict) for c in cmds),'missing commands')
    require(tuple(c.get('name') for c in cmds)==COMMAND_SCHEDULE,'wrong command schedule')
    require(all(type(c.get('exit_code')) is int and type(c.get('expected_exit')) is int and c['exit_code']==c['expected_exit']==(2 if c['name'] in NEGATIVE else 0) and not c.get('timed_out') for c in cmds),'unexpected command exit')
    require(r.get('real_host_consumption_verified') is False,'synthetic events do not prove real consumption')
    return {'checks':len(names),'commands':len(cmds)}
def validate_unit_payload(r):
    require(isinstance(r,dict) and r.get('result')=='PASS','unit failed')
    rows=r.get('scenarios');require(isinstance(rows,list) and all(isinstance(s,dict) for s in rows),'missing scenarios')
    require(tuple(s.get('name') for s in rows)==UNIT_SCENARIOS,'wrong scenario names/order')
    require(type(r.get('scenario_count')) is int and r['scenario_count']==len(UNIT_SCENARIOS),'wrong scenario count')
    require(all(s.get('status')=='PASS' and type(s.get('assertions')) is int and s['assertions']>0 for s in rows),'failed scenario')
    require(type(r.get('checks')) is int and r['checks']==107 and sum(s['assertions'] for s in rows)==r['checks'],'incorrect assertion total')
    return {'scenarios':len(rows),'assertions':r['checks']}
def validate_unit(r,*,source_commit,binary_sha256,script_sha256,test_sha256,native=True):
    identity(r,source_commit,binary_sha256,script_sha256,native)
    require(r.get('test_sha256')==test_sha256 and type(r.get('exit_code')) is int and r['exit_code']==0,'wrong test or failed execution')
    return validate_unit_payload(r)
