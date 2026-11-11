import json
from pathlib import Path

import pytest

from tpc_service.sessions.em_qualification import source_identity
from tpc_service.sessions.native import file_digest
from tpc_service.sessions.linear_sp import check_exploratory_source, verify_exploratory_matrix


def fixture_source(tmp_path, monkeypatch):
    folder = tmp_path / 'session'
    (folder / 'jobs').mkdir(parents=True)
    project_path = tmp_path / 'test.cst'
    project_path.write_bytes(b'project')
    result = project_path.with_suffix('') / 'Result'
    result.mkdir(parents=True)
    log = result / 'Model.log'; log.write_bytes(b'original log')
    storage = result / 'Storage.sdb'; storage.write_bytes(b'original data')
    original = {'job_id': 'em1', 'operation': 'solve', 'params': {'project_id': 'p'},
                'status': 'failed', 'error': {'code': 'session_solve_unverified'}}
    (folder / 'jobs' / 'em1.json').write_text(json.dumps(original))
    data = {'run_id': 7, 'port_ids': [1, 2], 'matrix_sha256': 'original', 'parameters': {'x': 1.0}}
    proof = {'purpose': 'exploratory_ads_handoff', 'source_job_id': 'em1',
             'source_job_identity': source_identity(original), 'workflow_revision': 'revision',
             'em_generation': 2, 'native_files': {str(log): file_digest(log)}, 'saved_matrix': data}
    qualification = {'job_id': 'qual1', 'operation': 'qualify_exploratory_em', 'status': 'succeeded',
                     'params': {'project_id': 'p'}, 'result': proof}
    (folder / 'jobs' / 'qual1.json').write_text(json.dumps(qualification))
    project = {'project_id': 'p', 'path': str(project_path), 'workflow': {
        'revision': 'revision', 'em_generation': 2, 'values': {'x': 1.0},
        'spec': {'parameters': {'x': {'affects': 'em'}}}}}
    monkeypatch.setattr('tpc_service.sessions.linear_sp.saved_curves', lambda *args: data)
    return folder, project, log, original


def test_source_requires_same_original_log_and_saved_matrix(tmp_path, monkeypatch):
    folder, project, log, _ = fixture_source(tmp_path, monkeypatch)
    proof = check_exploratory_source(folder, project, 'qual1')
    assert proof['source_job_id'] == 'em1'
    log.write_bytes(b'changed log')
    with pytest.raises(ValueError): check_exploratory_source(folder, project, 'qual1')


def test_source_rejects_changed_input_generation(tmp_path, monkeypatch):
    folder, project, _, _ = fixture_source(tmp_path, monkeypatch)
    project['workflow']['em_generation'] += 1
    with pytest.raises(ValueError): check_exploratory_source(folder, project, 'qual1')


def test_exported_matrix_is_compared_with_each_native_curve(tmp_path, monkeypatch):
    import numpy as np
    from cst_automation import embedded_network
    folder, project, _, _ = fixture_source(tmp_path, monkeypatch)
    f = np.array([1., 2., 3.]); matrix = np.array([[[.1, .2], [.3, .4]]] * 3, complex)
    path = tmp_path / 'matrix.npz'
    np.savez(path, frequency_hz=f, S=matrix, ports=np.array([1, 2]))
    p = dict(project_id='p', em_job_id='em1', run_id=7, matrix_path=str(path),
        matrix_sha256=embedded_network.digest(path), physical_port_ids=[1, 2],
        native_reference_ohms=[50, 50], reference_ohm=50,
        low_frequencies_hz=f.tolist(), frequency_atol_hz=.01,
        block_name='N', expected_payload_sha256='0'*64, output_path=str(tmp_path/'out.s2p'),
        settings=dict(accuracy_abs=.001, maximum_poles=10, enhance_dc=True, passivate=True),
        limits=dict(fit_max_error=.001, dc_solve_residual=.001, dc_max_singular=1.01,
                    dc_reciprocity_error=.001, roundtrip_error=.001,
                    native_matrix_error=.001, native_sample_residual=.001))
    qual_path = folder/'jobs'/'qual1.json'
    q = json.loads(qual_path.read_text())
    q['params'].update(run_id=7, port_ids=[1, 2], required_frequencies_hz=f.tolist(),
                       frequency_atol_hz=.01, max_residual=.001)
    qual_path.write_text(json.dumps(q))
    def curves(path, options, values, *, consume=None):
        if consume:
            for i, row in enumerate([1, 2]):
                for j, col in enumerate([1, 2]): consume(row, col, f, matrix[:, i, j])
        return q['result']['saved_matrix']
    monkeypatch.setattr('tpc_service.sessions.linear_sp.saved_curves', curves)
    assert verify_exploratory_matrix(folder, project, 'qual1', p)['max_matrix_error'] == 0
    matrix[0, 0, 1] = .8
    with pytest.raises(ValueError): verify_exploratory_matrix(folder, project, 'qual1', p)
