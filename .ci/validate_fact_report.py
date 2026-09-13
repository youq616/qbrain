"""Fail-closed N47A process evidence. Counts describe executed cases, not truth."""
from test_fact_process import EXPECTED_CHECKS


def require(ok, message):
    if not ok:
        raise ValueError(message)


def validate_report(r, *, source_commit, binary_sha256, script_sha256, native=True):
    require(isinstance(r,dict) and r.get('result')=='PASS','fact process did not pass')
    require(r.get('source_commit')==source_commit and r.get('tracked_tree_clean') is True,'wrong or dirty fact source')
    require(r.get('binary_sha256')==binary_sha256 and r.get('script_sha256')==script_sha256,'wrong fact executable/script')
    if native:
        require(r.get('native_windows') is True,'Windows fact evidence required')
    checks=r.get('checks'); require(isinstance(checks,list),'missing fact checks')
    require(all(isinstance(c,dict) and c.get('status')=='PASS' for c in checks),'failed fact check')
    names=[c.get('name') for c in checks]
    require(len(names)==len(EXPECTED_CHECKS) and set(names)==EXPECTED_CHECKS,'missing or duplicate fact cases')
    require(type(r.get('check_count')) is int and r['check_count']==len(names),'wrong fact check count')
    counts=r.get('counts')
    require(isinstance(counts,dict) and set(counts)=={'total','pass','fail'} and
            all(type(v) is int for v in counts.values()) and
            counts=={'total':len(names),'pass':len(names),'fail':0},'wrong fact totals')
    commands=r.get('commands')
    require(isinstance(commands,list) and len(commands)==56,'incomplete fact command history')
    require(all(isinstance(c,dict) and type(c.get('exit_code')) is int and
                type(c.get('expected_exit')) is int and c['expected_exit'] in (0,1) and
                c['exit_code']==c['expected_exit'] for c in commands),'unexpected fact command exit')
    require('error' not in r and 'error_type' not in r,'failure metadata cannot certify success')
    return {'named_checks':len(names),'commands':len(commands)}


def validate_unit_report(r, *, source_commit, binary_sha256, test_sha256,
                         expected_scenarios, native=True, require_clean=True):
    require(isinstance(r,dict) and r.get('result')=='PASS','fact unit did not pass')
    require(r.get('source_commit')==source_commit,'wrong unit source')
    if require_clean:
        require(r.get('tracked_tree_clean') is True,'dirty unit source')
    if native:
        require(r.get('native_windows') is True,'Windows fact unit evidence required')
    require(r.get('binary_sha256')==binary_sha256 and r.get('test_sha256')==test_sha256,
            'wrong unit binary/test source')
    require(type(r.get('exit_code')) is int and r['exit_code']==0,'unit exit failed')
    rows=r.get('scenarios');require(isinstance(rows,list),'missing scenarios')
    require(len(expected_scenarios)==14 and len(set(expected_scenarios))==14,'unexpected fact registry')
    require(len(rows)==14 and all(isinstance(x,dict) for x in rows),'incomplete fact scenarios')
    require([x.get('name') for x in rows]==expected_scenarios,'wrong fact scenario order or names')
    require(all(x.get('status')=='PASS' and type(x.get('assertions')) is int and x['assertions']>0
                for x in rows),'scenario failure or missing assertions')
    require(type(r.get('scenario_count')) is int and r['scenario_count']==len(rows),'scenario count mismatch')
    require(type(r.get('checks')) is int and r['checks']>=366 and
            sum(x['assertions'] for x in rows)==r['checks'],'assertion counts mismatch')
    require(r.get('provider_calls') is False and 'error_type' not in r,'unit scope/status mismatch')
    return {'scenarios':len(rows),'assertions':r['checks']}
