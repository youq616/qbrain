"""N47L complete process/unit evidence gates. No inference from a PASS label alone."""
from test_multiterm_process import EXPECTED_CHECKS, EXPECTED_COMMAND_COUNT

UNIT_SCENARIOS = ('explicit modes validate before lazy schema initialization', 'default and explicit literal retain exact legacy output bytes', 'all terms match one anchor and never combine separate facts', 'any terms use union without duplicate anchors and preserve ordering', 'ASCII separators and duplicate term bounds are explicit', 'mixed scripts and negation preserve full user evidence', 'original query bytes include all whitespace before splitting', 'whole sensitive input is rejected before token boundaries', 'SQL and wildcard text stay literal bound values', 'matching precedes candidate cap and source predicate filters', 'archived nonmatching counterclaims remain complete', 'matching neighbors keep independent one-hop counter-evidence', 'forget expiry and tamper invalidate both modes without revival', 'byte and result bounds preserve entire multi-term groups', 'term recall does not write or control caller transactions', 'multi-term anchors and neighbors share one actual WAL snapshot')


def require(ok,message):
    if not ok:raise ValueError(message)

def identity(r,source_commit,binary_sha256,script_sha256,native):
    require(isinstance(r,dict) and r.get('result')=='PASS','multiterm test failed')
    require(r.get('source_commit')==source_commit and r.get('tracked_tree_clean') is True,'wrong/dirty source')
    require(r.get('binary_sha256')==binary_sha256 and r.get('script_sha256')==script_sha256,'wrong binary/script')
    require(r.get('native_windows') is native,'wrong execution platform')
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
    require(type(r.get('checks')) is int and r['checks']>=258 and sum(x['assertions'] for x in rows)==r['checks'],'wrong assertion totals')
    return {'scenarios':len(rows),'assertions':r['checks']}
