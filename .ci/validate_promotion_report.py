"""N47E complete process/unit evidence gates. No inference from a PASS label alone."""
from test_promotion_process import EXPECTED_CHECKS, EXPECTED_COMMAND_COUNT

UNIT_SCENARIOS = ('local no-match events do not initialize fact schema', 'all local categories preserve full original quotes and negation', 'same-event replay and equal messages are idempotent', 'independent equal events attach without merging manual predicates', 'retired equal quotes veto automatic promotion across predicates', 'superseded statements stay retired when repeated', 'support cap is explicit and never creates overflow facts', 'strict IDs local method and source boundaries', 'all evidence preflight rejects invalid batches before initialization', 'fact and evidence batch rollback is atomic on injected failure', 'failed first batch may leave prepared schema but no fact writes', 'support forgetting retains remaining evidence and removes final copies', 'wall-clock expiry blocks promotion and recall', 'maximum batch has bounded receipts and no implicit relations', 'caller transactions are never committed or rolled back by promotion', 'new support renews only historically intact expired active facts', 'independent connections promote one event exactly once', 'promoted facts feed existing context without changing legacy tables')


def require(ok,message):
    if not ok:raise ValueError(message)

def identity(r,source_commit,binary_sha256,script_sha256,native):
    require(isinstance(r,dict) and r.get('result')=='PASS','promotion test failed')
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
    require(type(r.get('checks')) is int and r['checks']>=237 and sum(x['assertions'] for x in rows)==r['checks'],'wrong assertion totals')
    return {'scenarios':len(rows),'assertions':r['checks']}


def validate_install(r,*,source_commit,binary_sha256,script_sha256,installer_sha256,shell_major):
    require(isinstance(r,dict) and r.get('result')=='PASS','installer failed')
    require(r.get('source_commit')==source_commit and r.get('native_windows') is True and r.get('tracked_tree_clean') is True,'wrong native installer source')
    require(r.get('binary_sha256')==binary_sha256 and r.get('script_sha256')==script_sha256 and r.get('installer_sha256')==installer_sha256,'wrong installer bytes')
    require(type(r.get('shell_major')) is int and r['shell_major']==shell_major,'wrong PowerShell version')
    require(r.get('real_host_consumption_verified') is False,'fixture cannot prove consumption')
    require('error' not in r and 'error_type' not in r,'failed installer metadata')
    cases=('promotion_requires_capture_before_writes', 'default_all_optins_off', 'default_status_off', 'capture_only_not_promotion', 'explicit_promotion_not_recall', 'effective_status_on', 'installed_flag_promotes_actual_event', 'actual_promotion_trace', 'three_flags_complete_pipeline', 'malformed_boolean_off', 'capture_dependency_status_off', 'local_dependency_status_off', 'disabled_config_status_off', 'reinstall_resets_promotion', 'uninstall_disables_promotion', 'fixture_not_live_consumption')
    expected=[h+' '+c for h in ('Claude','Codex') for c in cases]+['global_client_config_unchanged']
    rows=r.get('checks');require(isinstance(rows,list) and all(isinstance(x,dict) for x in rows),'missing install cases')
    require([x.get('name') for x in rows]==expected and all(x.get('status')=='PASS' for x in rows),'partial install report')
    require(type(r.get('check_count')) is int and r['check_count']==33,'wrong installer count')
    return {'checks':len(rows),'shell_major':shell_major}
