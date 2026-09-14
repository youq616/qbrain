"""N47D complete process/unit evidence gates. No inference from a PASS label alone."""
from test_hook_fact_process import EXPECTED_CHECKS, EXPECTED_COMMAND_COUNT

UNIT_SCENARIOS = ('lazy opt-in composition retains ordinary memory without migration', 'one context retains counterclaim and suppresses duplicate raw quotes', 'entire serialized envelope obeys exact byte boundary', 'one item budget prioritizes complete fact neighborhoods', 'lexical terms share one query and empty prompts do not enumerate facts', 'invalid prompt flags budgets and secrets fail closed', 'retracted and superseded claims do not return via ordinary memory', 'fact groups refresh independently of memory dedup and revision changes', 'invalid expired or forgotten evidence cannot reenter either lane', 'source isolation applies to both lanes and quote suppression', 'failed composition rolls back only its own read transaction', 'wall clock expiry is rechecked without persisted fact context', 'both context lanes use one snapshot across a committed WAL forget')


def require(ok,message):
    if not ok:raise ValueError(message)

def identity(r,source_commit,binary_sha256,script_sha256,native):
    require(isinstance(r,dict) and r.get('result')=='PASS','recall test failed')
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
    require(type(r.get('checks')) is int and r['checks']>=229 and sum(x['assertions'] for x in rows)==r['checks'],'wrong assertion totals')
    return {'scenarios':len(rows),'assertions':r['checks']}


def validate_install(r,*,source_commit,binary_sha256,script_sha256,installer_sha256,shell_major):
    require(isinstance(r,dict) and r.get('result')=='PASS','installer failed')
    require(r.get('source_commit')==source_commit and r.get('native_windows') is True and r.get('tracked_tree_clean') is True,'wrong native installer source')
    require(r.get('binary_sha256')==binary_sha256 and r.get('script_sha256')==script_sha256 and r.get('installer_sha256')==installer_sha256,'wrong installer bytes')
    require(type(r.get('shell_major')) is int and r['shell_major']==shell_major,'wrong PowerShell version')
    require(r.get('real_host_consumption_verified') is False,'fixture cannot prove consumption')
    cases=('default_fact_off','default_status_off','default_capture_off','explicit_fact_on','fact_not_capture_consent','matching_optin_status','installed_flag_reaches_native_hook','capture_only_fact_off','capture_only_capture_on','capture_only_status_off','independent_flags_both_on','malformed_boolean_not_reported_enabled','reinstall_resets_optins','uninstall_disables_owned_config','uninstalled_status','fixture_not_live_model_consumption')
    expected=[h+' '+c for h in ('Claude','Codex') for c in cases]+['global_client_config_unchanged']
    rows=r.get('checks');require(isinstance(rows,list) and all(isinstance(x,dict) for x in rows),'missing install cases')
    require([x.get('name') for x in rows]==expected and all(x.get('status')=='PASS' for x in rows),'partial install report')
    require(type(r.get('check_count')) is int and r['check_count']==33,'wrong installer count')
    return {'checks':len(rows),'shell_major':shell_major}
