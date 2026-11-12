"""Catch stale or incomplete engineering handoffs without starting CST."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest
from cst_automation.process import hidden_console_flags


SCRIPT = Path(__file__).resolve().parents[1] / 'skills/cst-sessions/scripts/check_workflow.py'


@pytest.fixture
def checker():
    assert SCRIPT.is_file(), 'Missing executable workflow checkpoint checker'
    spec = importlib.util.spec_from_file_location('check_workflow', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def case(tmp_path):
    artifact = tmp_path / 'readback.json'
    artifact.write_text('{"ports":{"source":75},"fit":true}', encoding='utf-8')
    manifest = {
        'schema_version': 1,
        'identity': {'project_id': 'example', 'recovery_reference': 'example-ref'},
        'inputs': {'geometry_revision': 'A', 'source_ohm': 75},
        'stages': {'hb': ['source', 'fit']},
        'requirements': {
            'source': {'expected': 75, 'depends_on': ['source_ohm']},
            'fit': {'expected': True, 'depends_on': ['geometry_revision']},
        },
        'observations': {},
    }
    return manifest, artifact


def observe(checker, manifest, artifact):
    for name, pointer in [('source', '/ports/source'), ('fit', '/fit')]:
        manifest['observations'][name] = {
            'basis_sha256': checker.basis_digest(manifest, name),
            'path': artifact.name,
            'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
            'pointer': pointer,
        }


def test_missing_readback_is_not_configuration_success(checker, case):
    manifest, artifact = case
    result = checker.check(manifest, 'hb', artifact.parent)
    assert not result['consistent']
    assert {x['requirement'] for x in result['blockers']} == {'source', 'fit'}


def test_current_evidence_and_changed_geometry(checker, case):
    manifest, artifact = case
    observe(checker, manifest, artifact)
    assert checker.check(manifest, 'hb', artifact.parent)['consistent']
    manifest['inputs']['geometry_revision'] = 'B'
    result = checker.check(manifest, 'hb', artifact.parent)
    assert [(x['requirement'], x['code']) for x in result['blockers']] == [('fit', 'stale_basis')]


def test_source_change_does_not_accept_old_observation(checker, case):
    manifest, artifact = case
    observe(checker, manifest, artifact)
    manifest['requirements']['source']['expected'] = 90
    assert not checker.check(manifest, 'hb', artifact.parent)['consistent']


def test_other_project_cannot_reuse_evidence(checker, case):
    manifest, artifact = case
    observe(checker, manifest, artifact)
    manifest['identity']['project_id'] = 'different'
    assert len(checker.check(manifest, 'hb', artifact.parent)['blockers']) == 2


@pytest.mark.parametrize('mode', ['overwrite', 'missing', 'wrong_value', 'boolean_as_number', 'missing_node'])
def test_bad_artifacts_block_handoff(checker, case, mode):
    manifest, artifact = case
    observe(checker, manifest, artifact)
    if mode == 'missing':
        artifact.unlink()
    elif mode == 'missing_node':
        manifest['observations']['source']['pointer'] = '/ports/missing'
    else:
        content = ('{"ports":{"source":75},"fit":1}' if mode == 'boolean_as_number'
                   else '{"ports":{"source":50},"fit":true}')
        artifact.write_text(content, encoding='utf-8')
        if mode in ('wrong_value', 'boolean_as_number'):
            for obs in manifest['observations'].values():
                obs['sha256'] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert not checker.check(manifest, 'hb', artifact.parent)['consistent']


@pytest.mark.parametrize('mutation', ['empty_stage', 'unknown_requirement', 'unknown_input', 'unknown_stage'])
def test_incomplete_checklist_is_rejected(checker, case, mutation):
    manifest, artifact = case
    observe(checker, manifest, artifact)
    if mutation == 'empty_stage':
        manifest['stages']['hb'] = []
    elif mutation == 'unknown_requirement':
        manifest['stages']['hb'].append('missing')
    elif mutation == 'unknown_input':
        manifest['requirements']['source']['depends_on'].append('missing')
    with pytest.raises(ValueError):
        checker.check(manifest, 'unknown' if mutation == 'unknown_stage' else 'hb', artifact.parent)


def test_cli_exit_status_and_no_mutation(checker, case):
    manifest, artifact = case
    path = artifact.parent / 'workflow.json'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    before = path.read_bytes()
    result = subprocess.run([sys.executable, str(SCRIPT), str(path), '--stage', 'hb'], capture_output=True, text=True, creationflags=hidden_console_flags())
    assert result.returncode == 1
    assert not json.loads(result.stdout)['consistent']
    assert path.read_bytes() == before
    observe(checker, manifest, artifact)
    path.write_text(json.dumps(manifest), encoding='utf-8')
    result = subprocess.run([sys.executable, str(SCRIPT), str(path), '--stage', 'hb'], capture_output=True, text=True, creationflags=hidden_console_flags())
    assert result.returncode == 0
    assert json.loads(result.stdout)['consistent']


def test_json_pointer_array_and_escaped_keys(checker):
    assert checker.json_pointer({'a/b': [{'~key': 8}]}, '/a~1b/0/~0key') == 8
    with pytest.raises(ValueError):
        checker.json_pointer([8], '/-1')


def test_cli_malformed_manifest_fails_closed(checker, tmp_path):
    path = tmp_path / 'bad.json'
    path.write_text('[]', encoding='utf-8')
    result = subprocess.run([sys.executable, str(SCRIPT), str(path), '--stage', 'hb'], capture_output=True, text=True, creationflags=hidden_console_flags())
    assert result.returncode == 2
    assert not json.loads(result.stdout)['consistent']
