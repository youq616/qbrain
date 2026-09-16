"""N47H complete process/unit evidence gates. No inference from a PASS label alone."""
from test_lifecycle_candidate_process import EXPECTED_CHECKS, EXPECTED_COMMAND_COUNT

UNIT_SCENARIOS = ('empty discovery is read only without initializing optional modules', 'stale discovery returns metadata and explicit batch input only', 'restore selects live archived facts independently of advisory age', 'strict operation cursor predicate and budget validation', 'latest valid support and strict stored times control stale eligibility', 'invalid expired deleted and retired evidence is never suggested', 'source predicate and arbitrary seek keys never grant cross source access', 'damaged oversize quotes and unusable revisions are filtered before load', 'corrupt archive metadata fails closed without writing', 'scan limit yields an empty continuation without losing older eligible rows', 'static keyset pagination matches an independent complete sorted inventory', 'deleting the previous seek key does not break continuation', 'output interruption does not consume the unreturned candidate', 'evidence work interruption resumes from the unfinished row', 'candidate reads preserve caller transactions and deny all writes', 'selection is not a lease and new support invalidates its revision', 'one call uses a coherent snapshot when a second WAL connection forgets')


def require(ok,message):
    if not ok:raise ValueError(message)

def identity(r,source_commit,binary_sha256,script_sha256,native):
    require(isinstance(r,dict) and r.get('result')=='PASS','lifecycle test failed')
    require(r.get('source_commit')==source_commit and r.get('tracked_tree_clean') is True,'wrong/dirty source')
    require(r.get('binary_sha256')==binary_sha256 and r.get('script_sha256')==script_sha256,'wrong binary/script')
    if native:require(r.get('native_windows') is True,'Windows execution required')
    require('error' not in r and 'error_type' not in r,'failure metadata cannot certify success')

def validate_process(r,*,source_commit,binary_sha256,script_sha256,native=True):
    identity(r,source_commit,binary_sha256,script_sha256,native)
    checks=r.get('checks');require(isinstance(checks,list),'missing checks')
    require(all(isinstance(c,dict) and c.get('status')=='PASS' for c in checks),'failed check')
    names=[c.get('name') for c in checks]
    require(len(names)==len(EXPECTED_CHECKS) and set(names)==EXPECTED_CHECKS,'missing/duplicate checks')
    require(type(r.get('check_count')) is int and r['check_count']==len(names),'wrong count')
    counts=r.get('counts')
    require(isinstance(counts,dict) and set(counts)=={'total','pass','fail'} and
            all(type(n) is int for n in counts.values()) and
            counts=={'total':len(names),'pass':len(names),'fail':0},'wrong summary')
    commands=r.get('commands');require(isinstance(commands,list) and len(commands)==EXPECTED_COMMAND_COUNT,'incomplete commands')
    require(all(isinstance(c,dict) and type(c.get('exit_code')) is int and type(c.get('expected_exit')) is int and
                c['expected_exit'] in (0,1) and c['exit_code']==c['expected_exit'] and not c.get('timed_out')
                for c in commands),'bad command exit')
    require(r.get('real_host_consumption_verified') is False,'fixture cannot prove consumption')
    return {'checks':len(names),'commands':len(commands)}

def validate_unit(r,*,source_commit,binary_sha256,script_sha256,test_sha256,native=True):
    identity(r,source_commit,binary_sha256,script_sha256,native)
    require(r.get('test_sha256')==test_sha256,'wrong unit source')
    require(type(r.get('exit_code')) is int and r['exit_code']==0,'unit command failed')
    return validate_unit_payload(r)

def validate_unit_payload(r):
    require(isinstance(r,dict) and r.get('result')=='PASS','unit payload failed')
    rows=r.get('scenarios');require(isinstance(rows,list) and all(isinstance(x,dict) for x in rows),'missing scenarios')
    require(tuple(x.get('name') for x in rows)==UNIT_SCENARIOS,'wrong scenario set/order')
    require(type(r.get('scenario_count')) is int and r['scenario_count']==len(UNIT_SCENARIOS),'wrong scenario count')
    require(all(x.get('status')=='PASS' and type(x.get('assertions')) is int and x['assertions']>0 for x in rows),'failed scenario')
    require(type(r.get('checks')) is int and r['checks']>=647 and sum(x['assertions'] for x in rows)==r['checks'],'wrong assertion totals')
    return {'scenarios':len(rows),'assertions':r['checks']}

