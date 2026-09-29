"""Independent semantic replay of the fixed 42-command SQLite lifecycle review.
No producer imports, no process/SQL execution. Reconstruct inputs, evidence IDs and
all JSON outputs; initialization paths and competing duplicate winners may vary.
"""
from __future__ import annotations
import hashlib
import json

QUOTES = ('I prefer local C++ and do not permit automatic publication. 中文😀',
          '我决定保留完整原话，而不是模型推断。')


def require(ok, label):
    if not ok:
        raise ValueError(label)


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def equal(a, b, label):
    require(encode(a) == encode(b), label)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, 'lifecycle duplicate JSON key')
            out[k] = v
        return out
    def invalid(_):
        raise ValueError('lifecycle nonfinite JSON')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)


def payload(fragment='original', expiry=None):
    p = dict(session_id='first-session-独立', fragment_id=fragment, messages=[
        dict(role='user', content=QUOTES[0]),
        dict(role='assistant', content='I prefer ASSISTANT_FALSE_FACT.'),
        dict(role='tool', content='I decided TOOL_FALSE_FACT.'),
        dict(role='unknown', content='I prefer UNKNOWN_FALSE_FACT.'),
        dict(role='user', content=QUOTES[1])])
    if expiry is not None:
        p['expires_at'] = expiry
    if fragment == 'new-session':
        p['session_id'] = 'second-session-独立'
    if fragment == 'secret':
        p['messages'][0]['content'] = 'api_key=synthetic-review-secret'
    return p


def event_id(p, source='alpha'):
    body = encode(dict(messages=p['messages'], expires_at=p.get('expires_at', 0)))
    return digest(encode(['qbrain-memory-v1', source, p['session_id'], p['fragment_id'], digest(body)]))


def summary(p, source='alpha', state='archived', duplicate=False):
    return dict(event_id=event_id(p, source), source_id=source, status=state,
                evidence_live=state != 'forgotten', duplicate=duplicate,
                attempts=0 if state == 'archived' else 1)


def validate(records, streams):
    require(len(records) == len(streams) == 42, 'lifecycle fixed schedule')
    p = {name: payload(name) for name in ('original','other-only','new-session','edited','manual','model-denied','secret','race')}
    p.update(expired=payload('expired',1), future=payload('far-future',253402300799))
    # kind, payload key or permitted evidence keys, source, brain; all fixed order.
    schedule = [('init',None,'alpha','primary'),('init',None,'alpha','other')]
    def row(kind, key=None, source='alpha', brain='primary'):
        return (kind,key,source,brain)
    schedule += [row('capture','original'),row('read',[]),row('extract','original'),row('read',['original']),
        row('read',[],source='beta'),row('uninitialized',[],brain='other'),row('capture','other-only',brain='other'),
        row('missing','original',brain='other'),row('capture','new-session'),row('extract','new-session'),
        row('read',['original','new-session']),row('forget','original'),row('read',['new-session']),
        row('forget','new-session'),row('read',[]),row('replay','original'),row('forgotten','original'),
        row('capture','edited'),row('unavailable','edited'),row('forget','edited'),row('capture','expired'),
        row('unavailable','expired'),row('capture','future'),row('extract','future'),row('read',['future']),
        row('off','manual'),row('manual','manual'),row('extract','manual'),row('denied','future'),
        row('capture','model-denied'),row('model','model-denied'),row('secret','secret')]
    schedule += [row('concurrent','race',source='beta') for _ in range(8)]
    require(len(schedule) == 42, 'lifecycle oracle schedule')
    winners = 0
    for i, ((kind,key,source,brain), record, raw) in enumerate(zip(schedule,records,streams)):
        require(set(record) == {'brain','args','exit','hashes'}, 'lifecycle record fields')
        require(set(raw) == {'stdin','stdout','stderr'}, 'lifecycle stream fields')
        args = ['init']
        request = b''
        expected = None
        code = 0
        if kind != 'init':
            action = {'uninitialized':'read','missing':'status','replay':'capture','forgotten':'extract',
                      'unavailable':'extract','off':'capture','manual':'capture','denied':'extract',
                      'model':'extract','secret':'capture','concurrent':'capture'}.get(kind,kind)
            args = ['memory',action,'--source',source]
            if action in ('extract','status','forget'):
                args += ['--event',event_id(p[key],source)]
            if kind == 'manual':
                args += ['--manual']
            if kind == 'model':
                args += ['--method','model']
            if action == 'capture':
                request = encode(p[key])
        equal(record['args'],args,'lifecycle exact arguments '+str(i))
        require(record['brain'] == brain and raw['stdin'] == request and raw['stderr'] == b'', 'lifecycle routing/request '+str(i))
        if kind == 'init':
            require(type(record['exit']) is int and record['exit'] == 0 and bool(raw['stdout']), 'lifecycle actual initialization')
            continue
        actual = decode(raw['stdout'])
        if kind in ('read','uninitialized'):
            allowed = {}
            for k in key:
                for idx,category,quote in ((0,'preference',QUOTES[0]),(4,'decision',QUOTES[1])):
                    eid = event_id(p[k],source)
                    candidate = dict(message_index=idx,category=category,quote=quote)
                    ident = digest(eid.encode()+encode(candidate))
                    allowed[ident] = dict(**candidate,item_id=ident,event_id=eid,session_id=p[k]['session_id'],source_id=source,
                        expires_at=p[k].get('expires_at',0),method='explicit-markers-v1',evidence_slug='sessions/'+eid)
            require(type(actual.get('items')) is list and len(actual['items']) == (2 if key else 0), 'lifecycle exact recall count')
            require(len({x.get('quote') for x in actual['items']}) == len(actual['items']), 'lifecycle quotation deduplication')
            for item in actual['items']:
                require(item.get('item_id') in allowed, 'lifecycle recalled evidence identity')
                equal(item,allowed[item['item_id']],'lifecycle whole attributed quote')
            expected = dict(initialized=kind!='uninitialized',items=actual['items'],source_id=source,truncated=False,
                            truth_status='caller_attested_user_statement',untrusted_data=True)
            if kind != 'uninitialized':
                expected['candidate_limit'] = 200
        elif kind in ('capture','manual','concurrent'):
            duplicate = kind == 'concurrent' and actual.get('duplicate') is True
            expected = summary(p[key],source,duplicate=duplicate)
            if not duplicate:
                expected.update(archived=True,extracted=False,provider_requests=0)
                if kind == 'concurrent':
                    winners += 1
        elif kind == 'extract':
            expected = dict(**summary(p[key],source,state='extracted'),item_count=2,error_code=None,
                method='explicit-markers-v1',provider_attempts=0,cost=None,cost_status='not_priced')
        elif kind == 'forget':
            expected = dict(event_id=event_id(p[key],source),status='forgotten',replay_suppressed=True)
        elif kind == 'replay':
            expected = summary(p[key],source,state='forgotten',duplicate=True)
        elif kind == 'off':
            expected = dict(archived=False,reason='writeback_off',status='skipped')
        else:
            code = 1
            error = {'missing':'event_not_found','forgotten':'event_forgotten','unavailable':'evidence_unavailable',
                     'denied':'writeback_off','model':'external_extraction_denied','secret':'sensitive_material_rejected'}[kind]
            expected = {'error':{'code':error}}
        require(type(record['exit']) is int and record['exit'] == code, 'lifecycle semantic exit')
        equal(actual,expected,'lifecycle exact result '+str(i))
    require(winners == 1,'lifecycle exactly one concurrent creator')
    return dict(commands=42,whole_results_recomputed=40,initializations=2,concurrent_creators=1)
