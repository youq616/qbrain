"""Offline checks of extracted N47L workflow validators; never publish or call GitHub.

Synthetic pin and asset fixtures test rejection behavior only. They do not
authenticate CI evidence, a review, a candidate package, or a release.
"""
import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from unittest.mock import patch


def check_template(raw, report):
    lines = raw.decode('utf-8').splitlines()
    # Read only the simple job-level quoted environment values and two Python
    # block scalars used by this exact template; no general YAML parser needed.
    env = {}
    blocks = []
    for index, line in enumerate(lines):
        match = re.fullmatch(r"      ([A-Z_0-9]+): '([^']*)'", line)
        if match:
            env[match[1]] = match[2]
        if line == '        run: |':
            body = []
            for row in lines[index + 1:]:
                if row and not row.startswith('          '):
                    break
                body.append(row[10:] if row else '')
            blocks.append('\n'.join(body) + '\n')
    assert len(blocks) == 2 and env['SOURCE_SHA'] == '17e9a435f94e45b3ca22d3da062ba4683c135c4b'
    for block in blocks:
        ast.parse(block)
    guard = compile(blocks[0], 'actual-template-preflight', 'exec')
    unresolved = any('REPLACE' in value for value in env.values())
    with patch.dict(os.environ, env, clear=True):
        try:
            exec(guard, {})
        except RuntimeError as error:
            assert unresolved, str(error)
            report['default_guard'] = {'result': 'REJECTED_UNRESOLVED_PINS', 'error': str(error)}
        else:
            assert not unresolved, 'Unresolved template became executable'
            report['default_guard'] = {'result': 'PIN_FORMATS_ACCEPTED_ONLY'}
    valid = dict(env)
    for name, value in valid.items():
        if 'REPLACE' in value:
            valid[name] = ('a' * 40 if name in ('REVIEW_SHA', 'REVIEW_TREE', 'MERGE_SHA')
                           else 'b' * 64 if name.endswith('SHA256') else '1')
    with patch.dict(os.environ, valid, clear=True):
        exec(guard, {})
    report['synthetic_pin_format_control'] = 'PASS'
    for field in valid:
        if field == 'PYTHONDONTWRITEBYTECODE':
            continue
        for malformed in ('', 'REPLACE_UNRESOLVED', 'invalid'):
            candidate = dict(valid, **{field: malformed})
            with patch.dict(os.environ, candidate, clear=True):
                try:
                    exec(guard, {})
                except RuntimeError as error:
                    report['pin_negatives'].append({'field': field, 'mutation': malformed,
                                                    'result': 'REJECTED', 'error': str(error)})
                else:
                    raise AssertionError('Pin accepted: ' + field + '/' + malformed)
    assert len(report['pin_negatives']) == 45

    program = ast.parse(blocks[1])
    helpers = [node for node in program.body if isinstance(node, ast.FunctionDef) and
               node.name in ('need', 'positive_int', 'asset_metadata', 'unique', 'obj', 'api')]
    assets = ['qbrain-windows-x64-multiterm.zip', 'PROVENANCE.json', 'SHA256SUMS.txt']
    expected = {name: {'size': len(data), 'digest': 'sha256:' + hashlib.sha256(data).hexdigest()}
                for name in assets for data in [('fixed original ' + name).encode()]}
    scope = {'assets': assets, 'expected_assets': expected, 'json': json,
             'subprocess': subprocess, 'repo': 'youq616/qbrain'}
    exec(compile(ast.Module(body=helpers, type_ignores=[]), 'actual-template-validators', 'exec'), scope)
    fixture = {'assets': [dict(name=name, id=100 + index, state='uploaded', **expected[name])
                          for index, name in enumerate(assets)]}
    validate = scope['asset_metadata']
    pins = validate(fixture)
    assert set(pins) == set(assets) and validate(copy.deepcopy(fixture), pins) == pins
    report['asset_controls'] = {'initial_draft': 'PASS', 'unchanged_pinned_assets': 'PASS'}
    first_edits = [
        ('missing_id', lambda r: r['assets'][0].pop('id')),
        ('boolean_id', lambda r: r['assets'][0].update(id=True)),
        ('duplicate_id', lambda r: r['assets'][1].update(id=r['assets'][0]['id'])),
        ('duplicate_name', lambda r: r['assets'][1].update(name=r['assets'][0]['name'])),
        ('missing_digest', lambda r: r['assets'][0].pop('digest')),
        ('null_digest', lambda r: r['assets'][0].update(digest=None)),
        ('wrong_digest', lambda r: r['assets'][0].update(digest='sha256:' + 'f' * 64)),
        ('wrong_size', lambda r: r['assets'][0].update(size=999)),
        ('boolean_size', lambda r: r['assets'][0].update(size=True)),
        ('incomplete_state', lambda r: r['assets'][0].update(state='starter')),
        ('missing_asset', lambda r: r['assets'].pop()),
        ('extra_asset', lambda r: r['assets'].append(copy.deepcopy(r['assets'][0]))),
    ]
    later_edits = [
        ('same_bytes_new_id', lambda r: r['assets'][0].update(id=900)),
        ('same_id_changed_digest', lambda r: r['assets'][0].update(digest='sha256:' + 'f' * 64)),
        ('new_id_same_size_changed_digest', lambda r: r['assets'][0].update(id=900, digest='sha256:' + 'f' * 64)),
        ('missing_digest_after_readback', lambda r: r['assets'][0].pop('digest')),
    ]
    for stage, edits in (('initial_draft', first_edits), ('again', later_edits), ('public', later_edits)):
        for name, edit in edits:
            bad = copy.deepcopy(fixture)
            edit(bad)
            try:
                validate(bad) if stage == 'initial_draft' else validate(bad, pins)
            except RuntimeError as error:
                report['asset_negatives'].append({'stage': stage, 'mutation': name,
                                                  'result': 'REJECTED', 'error': str(error)})
            else:
                raise AssertionError('Asset accepted: ' + stage + '/' + name)
    assert len(report['asset_negatives']) == 20
    for stage in ('again', 'public'):
        calls = [node for node in ast.walk(program) if isinstance(node, ast.Call) and
                 isinstance(node.func, ast.Name) and node.func.id == 'asset_metadata' and node.args and
                 isinstance(node.args[0], ast.Name) and node.args[0].id == stage]
        assert len(calls) == 1 and len(calls[0].args) == 2 and calls[0].args[1].id == 'uploaded_assets'
    report['both_post_upload_checks_use_original_pins'] = True

    for optional, code, stdout, stderr, expected_response in (
            (False, 0, b'{"id":1}', b'', {'id': 1}),
            (True, 1, b'{"message":"Not Found","status":"404"}', b'gh: Not Found (HTTP 404)', None)):
        with patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], code, stdout, stderr)):
            assert scope['api']('releases/tags/fixture', optional=optional) == expected_response
    for label, stdout, stderr in (
            ('rate_limit', b'{"message":"API rate limit exceeded","status":"403"}', b'gh: API rate limit exceeded (HTTP 403)'),
            ('network', b'', b'network unavailable'),
            ('authentication', b'{"message":"Not Found","status":"404"}', b'authentication failed')):
        with patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, stdout, stderr)):
            try:
                scope['api']('releases/tags/fixture', optional=True)
            except RuntimeError:
                report['api_negatives'].append({'mutation': label, 'result': 'REJECTED'})
            else:
                raise AssertionError('API error treated as absence: ' + label)
    report['api_controls'] = {'success': 'PASS', 'actual_404_absence': 'PASS'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('report must be a new path')
    raw = args.template.read_bytes()
    report = {'result': 'FAIL', 'template_sha256': hashlib.sha256(raw).hexdigest(),
              'scope': 'Offline execution of extracted template validators using synthetic fixtures; no repository changes, network or publication',
              'network_or_actual_publication': False, 'pin_negatives': [], 'asset_negatives': [], 'api_negatives': []}
    try:
        check_template(raw, report)
        report['result'] = 'PASS'
    except Exception as error:
        report.update(error_type=type(error).__name__, error=str(error))
    report['counts'] = {name: len(report[name]) for name in ('pin_negatives', 'asset_negatives', 'api_negatives')}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print(json.dumps({key: report[key] for key in ('result', 'template_sha256', 'counts')}))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
