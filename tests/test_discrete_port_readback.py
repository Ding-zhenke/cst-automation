from types import SimpleNamespace as NS
import pytest

from cst_solver.simulation.discrete_ports import read_discrete_ports
from tpc_service.sessions.inspection import inspect_native, validate_options
from tpc_service.errors import ServiceError


def fixture(coords=None, props=None, length=0.15, kind='Discrete'):
    calls = []
    def getter(name, value):
        def get(pid):
            calls.append((name, pid))
            return value
        return get
    native = NS(GetCoordinates=getter('coordinates', coords if coords is not None else (True, 0., 0., 0., 0., .15, 0.)),
                GetProperties=getter('properties', props if props is not None else (True, 'SParameter', 100., 1., 1., 0., 0., True)),
                GetLength=getter('length', length))
    app = NS(cst_file=NS(model3d=NS(Port=NS(GetType=getter('type', kind)), DiscretePort=native)))
    return app, calls


@pytest.mark.parametrize('ids', [None, [], [1, 1], [True], [0], [-1], ['1'], [1.0], [2**31], list(range(1, 1002))])
def test_bad_request_never_touches_native(ids):
    class Forbidden:
        def __getattr__(self, name):
            pytest.fail('Native access before input validation')
    with pytest.raises(ValueError):
        read_discrete_ports(Forbidden(), ids)
    with pytest.raises(ServiceError):
        validate_options(dict(native_readback=True, discrete_port_ids=ids))


def test_read_preserves_real_values_and_only_calls_getters():
    app, calls = fixture()
    report = read_discrete_ports(app, [1, 5])
    assert report['1']['properties']['impedance_ohms'] == 100.
    assert report['5']['start'] == [0., 0., 0.]
    assert report['5']['end'] == [0., .15, 0.]
    assert report['5']['raw']['properties'] == [True, 'SParameter', 100., 1., 1., 0., 0., True]
    assert calls == [('type', 1), ('type', 5), ('coordinates', 1), ('properties', 1), ('length', 1),
                     ('coordinates', 5), ('properties', 5), ('length', 5)]


@pytest.mark.parametrize('kwargs', [
    {'kind': 'Waveguide'}, {'coords': (False, 0, 0, 0, 1, 0, 0)},
    {'coords': (1, 0, 0, 0, 1, 0, 0)}, {'coords': (True, 0)},
    {'coords': (True, 0, 0, float('nan'), 1, 0, 0)},
    {'props': (False, 'SParameter', 50, 1, 1, 0, 0, True)},
    {'props': (True, 'Unknown', 50, 1, 1, 0, 0, True)},
    {'props': (True, 'Voltage', 50, 1, 1, 0, 0, 1)},
    {'props': (True, 'Current', '50', 1, 1, 0, 0, True)},
    {'length': float('inf')}, {'length': -1}, {'length': True},
])
def test_bad_native_output_is_not_verified(kwargs):
    app, _ = fixture(**kwargs)
    with pytest.raises(ValueError):
        read_discrete_ports(app, [1])
    result = inspect_native(app, dict(parameter_names=[], solid_names=[], discrete_port_ids=[1]))
    assert result['discrete_ports'] is None
    assert result['errors'][0]['query'] == 'discrete_ports'


def test_inspect_opt_in():
    with pytest.raises(ServiceError):
        validate_options(dict(discrete_port_ids=[1]))
    options = dict(native_readback=True, parameter_names=[], solid_names=[], discrete_port_ids=[1])
    validate_options(options)
    app, _ = fixture()
    report = inspect_native(app, options)
    assert not report['errors']
    assert report['discrete_ports']['1']['length'] == .15


def test_old_worker_refused_before_queue(tmp_path, monkeypatch):
    from tpc_service.sessions import manager as module
    from tpc_service.sessions.store import read, write
    manager = module.SessionManager(str(tmp_path), backend='fake')
    ref = manager.ensure('ports', 'ensure')
    folder = tmp_path / ref['session_id']
    state = read(folder / 'session.json')
    state.update(status='ready', worker={'pid': 123}, worker_capabilities=[])
    write(folder / 'session.json', state)
    monkeypatch.setattr(module, 'alive', lambda *a: True)
    monkeypatch.setattr(manager, '_launch', lambda *a: pytest.fail('No launch'))
    with pytest.raises(ServiceError) as exc:
        manager.submit(ref['session_id'], ref['credential'], 'r', 'inspect',
                       dict(project_id='p', native_readback=True, discrete_port_ids=[1]))
    assert exc.value.code == 'workflow_worker_upgrade_required'
    assert not list((folder / 'jobs').glob('*.json'))


@pytest.mark.parametrize('ids', [[1], [True]])
def test_execution_rechecks_before_acquiring_app(tmp_path, ids):
    from tpc_service.sessions.operations import execute
    runtime = NS(folder=tmp_path, backend='cst', state=lambda: {'worker_capabilities': []},
                 project=lambda *a: pytest.fail('No native acquisition'))
    job = dict(operation='inspect', params=dict(project_id='p', native_readback=True, discrete_port_ids=ids))
    with pytest.raises(ServiceError):
        execute(runtime, job)
    assert job['workflow_preflight_rejected']


@pytest.mark.parametrize('valid', [True, False])
def test_mcp_routes_and_rejects_before_launch(tmp_path, monkeypatch, valid):
    from cst_mcp import tools
    from cst_mcp.session_tools import register_session_tools
    from tpc_service.sessions import SessionManager
    for name in ('TOOL_SPECS', 'HANDLERS', 'READ_TOOLS', 'WRITE_TOOLS'):
        monkeypatch.setattr(tools, name, getattr(tools, name).copy())
    def launch(*args, **kwargs):
        if not valid:
            pytest.fail('Invalid read must not launch CST')
    monkeypatch.setattr(SessionManager, '_launch', launch)
    register_session_tools(str(tmp_path.resolve()), backend='fake')
    ref = tools.dispatch('ensure_cst_session', dict(binding='ports', request_id='ensure'))['session']
    result = tools.dispatch('submit_cst_session_operation', dict(session_id=ref['session_id'],
        credential=ref['credential'], request_id='r', operation='inspect',
        params=dict(project_id='p', native_readback=True, discrete_port_ids=[1] if valid else [False])))
    assert result['ok'] is valid
    if valid:
        assert result['job']['params']['discrete_port_ids'] == [1]
    else:
        assert not list((tmp_path / ref['session_id'] / 'jobs').glob('*.json'))
