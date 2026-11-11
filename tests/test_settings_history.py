"""Replay a saved history using CST's documented adjacent-caption replacement."""
import json
from types import SimpleNamespace

import pytest

from cst_solver.mesh.mesh import MeshMixin
from cst_solver.simulation.solver import SolverMixin
from tpc_service.sessions.model_api import dispatch
from tpc_service.errors import ServiceError


class History:
    def __init__(self):
        self.blocks = []

    def add_to_history(self, caption, code):
        if self.blocks and self.blocks[-1][0] == caption:
            self.blocks.pop()
        self.blocks.append((caption, code))

    def replay_saved(self, path):
        path.write_text(json.dumps(self.blocks), encoding='utf-8')
        state = {}
        for _, code in json.loads(path.read_text(encoding='utf-8')):
            for line in code.splitlines():
                line = line.strip()
                if line.startswith(('With ', 'End With')):
                    continue
                command, value = line.split(' ', 1)
                state[command] = value
        return state


class App(SolverMixin, MeshMixin):
    def __init__(self):
        self.history = History()
        self.cst_file = SimpleNamespace(model3d=self.history)


CASES = [
    ('configure_tetrahedral_mesh',
     {'adaptation': {'refinement_type': 'automatic', 'singular_edge_refinement': 2,
       'snap_to_geometry': True, 'min_passes': 2, 'max_passes': 12, 'refinement_percentage': 5},
      'local_solids': [{'solid': 'device:oxide', 'max_step': .0035}]},
     {'adaptation': {'snap_to_geometry': False}},
     {'MeshAdaption3D.SingularEdgeRefinement': '"2"', 'MeshAdaption3D.MaxPasses': '"12"',
      'Solid.SetMeshStepwidthTet': '"device:oxide", "0.0035"', 'MeshAdaption3D.SnapToGeometry': 'False'}),
    ('configure_fd_frequency', {'output_samples': 101, 'sweep_error': .01},
     {'output_samples': 3}, {'FDSolver.SetNumberOfResultDataSamples': '"3"',
                            'FDSolver.SetSweepThreshold': '"S-Parameters", "0.01"'}),
    ('configure_fd_parallelization', {'enabled': True, 'threads': 12, 'cpu_devices': 2},
     {'threads': 4}, {'FDSolver.UseParallelization': 'True', 'FDSolver.MaxCPUs': '"4"',
                     'FDSolver.MaximumNumberOfCPUDevices': '"2"'}),
    ('configure_fd_linear_solver', {'solver_type': 'Direct', 'tet_order': 'Second',
      'low_frequency_stabilization': True}, {'allow_float_direct_solver': False},
     {'.Type': '"Direct"', '.OrderTet': '"Second"', '.LowFrequencyStabilization': '"True"',
      '.SetAllowFloatDirectSolver': '"False"'}),
]


@pytest.mark.parametrize('method,full,sparse,expected', CASES)
def test_full_then_sparse_survives_save_replay(tmp_path, method, full, sparse, expected):
    app = App()
    result = dispatch(app, [{'method': method, 'args': [full]},
                           {'method': method, 'kwargs': {'settings': sparse}}])
    assert len(app.history.blocks) == 2
    for item, (caption, _) in zip(result['configuration_receipts'], app.history.blocks):
        assert item['receipt']['history_caption'] == caption
        assert item['receipt']['readback_verified'] is False
    assert app.history.replay_saved(tmp_path / 'history.json').items() >= expected.items()
    # Repeating identical content is stable and can compact only its identical predecessor.
    before = list(app.history.blocks)
    getattr(app, method)(sparse)
    assert app.history.blocks == before
    getattr(app, method)(full)
    assert len(app.history.blocks) == 3
    assert app.history.blocks[-1] == before[0]


@pytest.mark.parametrize('method,full,sparse,expected', CASES)
def test_invalid_last_call_rejects_entire_batch(method, full, sparse, expected):
    app = App()
    with pytest.raises(ServiceError):
        dispatch(app, [{'method': method, 'args': [full]},
                       {'method': method, 'args': [{'unknown': True}]}])
    assert app.history.blocks == []


def test_caption_normalizes_line_endings_but_preserves_command_content():
    from cst_automation.settings_history import history_caption
    assert history_caption('s', 'a\r\nb\r') == history_caption('s', 'a\nb\n')
    assert history_caption('s', 'a\nb') != history_caption('s', 'b\na')
    assert history_caption('s', 'a " x"') != history_caption('s', 'a "x"')


@pytest.mark.parametrize('method,full,sparse,expected', CASES)
@pytest.mark.parametrize('mixed', [False, True])
def test_old_worker_rejects_before_enqueue_or_launch(tmp_path, monkeypatch, method, full, sparse, expected, mixed):
    import hashlib
    from tpc_service.sessions import manager as module
    from tpc_service.sessions.store import read, write
    manager = module.SessionManager(str(tmp_path), backend='fake')
    ref = manager.ensure('history', 'ensure')
    folder = tmp_path / ref['session_id']
    state = read(folder / 'session.json')
    state.update(status='ready', worker={'pid': 123}, worker_capabilities=[
        'solver-settings-no-rebuild-v1', 'mesh-settings-no-rebuild-v1',
        'hf-tet-adaptation-controls-v1', 'hf-tet-order-controls-v1', 'hf-tet-lf-controls-v1'])
    write(folder / 'session.json', state)
    monkeypatch.setattr(module, 'alive', lambda *a: True)
    monkeypatch.setattr(manager, '_launch', lambda *a: pytest.fail('No worker launch'))
    calls = [{'method': method, 'kwargs': {'settings': sparse}}]
    if mixed:
        calls.insert(0, {'method': 'new_component', 'args': ['never']})
    params = dict(project_id='p', stage_id='history', calls=calls,
        preview_digest=hashlib.sha256(json.dumps(calls, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
    with pytest.raises(ServiceError) as error:
        manager.submit(ref['session_id'], ref['credential'], 'history', 'model_api', params)
    assert error.value.code == 'workflow_worker_upgrade_required'
    assert 'Content-bound' in str(error.value)
    assert not list((folder / 'jobs').glob('*.json'))


@pytest.mark.parametrize('method,full,sparse,expected', CASES)
def test_execution_rechecks_history_support_before_project(tmp_path, method, full, sparse, expected):
    from tpc_service.sessions.operations import execute
    runtime = SimpleNamespace(folder=tmp_path, backend='cst', state=lambda: {'worker_capabilities': []},
        project=lambda *a: pytest.fail('No native project access'))
    job = {'operation': 'model_api', 'params': {'project_id': 'p', 'calls': [
        {'method': 'new_component', 'args': ['never']}, {'method': method, 'args': [sparse]}]}}
    with pytest.raises(ServiceError) as error:
        execute(runtime, job)
    assert error.value.code == 'workflow_worker_upgrade_required'
    assert 'Content-bound' in str(error.value)
    assert job['workflow_preflight_rejected'] is True
