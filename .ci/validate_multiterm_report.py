"""N47L complete process/unit evidence gates. No inference from a PASS label alone."""
import json
import re
from test_multiterm_process import (EXPECTED_CHECKS, COMMAND_SCHEDULE, COMMAND_ARGUMENTS,
                                    COMMAND_INPUTS, NEGATIVE)

UNIT_SCENARIOS = ('explicit modes validate before lazy schema initialization', 'default and explicit literal retain exact legacy output bytes', 'all terms match one anchor and never combine separate facts', 'any terms use union without duplicate anchors and preserve ordering', 'ASCII separators and duplicate term bounds are explicit', 'mixed scripts and negation preserve full user evidence', 'original query bytes include all whitespace before splitting', 'whole sensitive input is rejected before token boundaries', 'SQL and wildcard text stay literal bound values', 'matching precedes candidate cap and source predicate filters', 'archived nonmatching counterclaims remain complete', 'matching neighbors keep independent one-hop counter-evidence', 'forget expiry and tamper invalidate both modes without revival', 'byte and result bounds preserve entire multi-term groups', 'term recall does not write or control caller transactions', 'multi-term anchors and neighbors share one actual WAL snapshot')


def require(ok,message):
    if not ok:raise ValueError(message)

def identity(r,source_commit,binary_sha256,script_sha256,native):
    require(isinstance(r,dict) and r.get('result')=='PASS','multiterm test failed')
    require(r.get('source_commit')==source_commit and r.get('tracked_tree_clean') is True,'wrong/dirty source')
    require(r.get('binary_sha256')==binary_sha256 and r.get('script_sha256')==script_sha256,'wrong binary/script')
    require(r.get('native_windows') is native,'wrong execution platform')
    require('error' not in r and 'error_type' not in r,'failure metadata cannot certify success')

def _matches(actual, pattern, bindings):
    if isinstance(pattern, str) and pattern.startswith('<id:') and pattern.endswith('>'):
        if not isinstance(actual, str) or re.fullmatch(r'[0-9a-f]{64}', actual) is None: return False
        if pattern in bindings: return bindings[pattern]==actual
        bindings[pattern] = actual
        return True
    if pattern=='<group-budget>':
        return (isinstance(actual,str) and re.fullmatch(r'[1-9][0-9]{2,4}',actual) is not None and
                512<=int(actual)<32768)
    if isinstance(pattern, dict) and set(pattern)=={'<json>'}:
        if not isinstance(actual, str): return False
        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result: raise ValueError('duplicate embedded JSON key')
                result[key] = value
            return result
        try: decoded=json.loads(actual,object_pairs_hook=unique_pairs)
        except (TypeError,ValueError): return False
        return _matches(decoded,pattern['<json>'],bindings)
    if type(actual) is not type(pattern): return False
    if isinstance(pattern, dict):
        return set(actual)==set(pattern) and all(_matches(actual[key],value,bindings) for key,value in pattern.items())
    if isinstance(pattern, list):
        return len(actual)==len(pattern) and all(_matches(a,p,bindings) for a,p in zip(actual,pattern))
    return actual==pattern

def validate_commands(commands):
    require(isinstance(commands,list) and len(commands)==len(COMMAND_SCHEDULE) and
            all(isinstance(c,dict) for c in commands),'incomplete commands')
    require(tuple(c.get('name') for c in commands)==COMMAND_SCHEDULE,'wrong command schedule')
    bindings = {}
    for command in commands:
        name = command['name']
        expected = 1 if name in NEGATIVE else 0
        require(type(command.get('exit_code')) is int and type(command.get('expected_exit')) is int and
                command['exit_code']==command['expected_exit']==expected and not command.get('timed_out'),
                'bad command exit: '+name)
        require(_matches(command.get('args'),COMMAND_ARGUMENTS[name],bindings),'wrong command arguments: '+name)
        require(_matches(command.get('stdin_json'),COMMAND_INPUTS[name],bindings),'wrong command input: '+name)

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
    commands=r.get('commands');validate_commands(commands)
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
