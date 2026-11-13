import hashlib,json
from types import SimpleNamespace
import pytest

def test_full_tensor_uses_owned_model_and_invalid_batch_has_no_side_effects():
    from tpc_service.sessions.model_api import dispatch
    from cst_solver.material.materials import MaterialMixin
    history = []
    class App(MaterialMixin):
        cst_file = SimpleNamespace(model3d=SimpleNamespace(
            add_to_history=lambda name, text: history.append((name, text))))
        def new_component(self, name):
            history.append(('component', name))
    identity = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    valid = {'method': 'create_material_full_tensor', 'args': ['tensor', identity, identity]}
    dispatch(App(), [valid])
    assert len(history) == 1 and 'tensor' in history[0][0]
    history.clear()
    invalid = {'method': 'create_material_full_tensor', 'args': ['tensor', identity, [[1]]]}
    with pytest.raises(Exception):
        dispatch(App(), [{'method': 'new_component', 'args': ['must-not-run']}, invalid])
    assert history == []

def params(calls):
    return dict(project_id='p', stage_id='s', calls=calls,
        preview_digest=hashlib.sha256(json.dumps(calls,sort_keys=True,ensure_ascii=False).encode()).hexdigest())

def test_calls_existing_python_api_in_order_and_rejects_late_bad_signature():
    from tpc_service.sessions.model_api import dispatch
    seen=[]
    app=SimpleNamespace(new_component=lambda name: seen.append(name))
    dispatch(app,[{'method':'new_component','args':['YIG']}])
    assert seen==['YIG']
    with pytest.raises(Exception):
        dispatch(app,[{'method':'new_component','args':['Cutters']},
                      {'method':'square','args':[]}])
    assert seen==['YIG']

def test_no_arbitrary_python_or_solver_execution():
    from tpc_service.sessions.model_api import validate_calls
    for name in ['run','close','__getattribute__','eval','project_open']:
        with pytest.raises(Exception):validate_calls([{'method':name}])

def test_stage_validation_accepts_only_reviewed_call_digest():
    from tpc_service.sessions.validation import validate
    p=params([{'method':'new_component','args':['YIG']}]);validate('model_api',p)
    p['preview_digest']='wrong'
    with pytest.raises(Exception):validate('model_api',p)


def test_geometry_families_are_explicitly_routed_without_sdk():
    from cst_solver import setup as CstSetup
    from tpc_service.sessions.model_api import METHODS
    required = {'create_triangular_prism', 'create_hexagonal_prism', 'create_wire',
                'create_circle', 'create_polygon', 'extrude_curve', 'insert', 'intersect',
                'translate', 'rotation', 'mirror', 'scale', 'create_material_custom',
                'create_material_tensor', 'create_discrete_port', 'create_lumped_element',
                'configure_fd_frequency', 'configure_tetrahedral_mesh'}
    assert required <= METHODS
    assert all(callable(getattr(CstSetup, name, None)) for name in METHODS)


def test_parameter_creation_is_reviewable_and_preflighted_before_geometry():
    from tpc_service.sessions.model_api import dispatch
    calls = []
    app = SimpleNamespace(para=lambda *args, **kwargs: calls.append(('para', args, kwargs)),
                          new_component=lambda name: calls.append(('component', name)))
    dispatch(app, [
        {'method': 'para', 'args': ['trace_w', 1.9],
         'kwargs': {'expression': 'Trace width in mm'}},
        {'method': 'new_component', 'args': ['Microstrip']},
    ])
    assert calls == [
        ('para', ('trace_w', 1.9), {'expression': 'Trace width in mm'}),
        ('component', 'Microstrip'),
    ]
    calls.clear()
    with pytest.raises(Exception):
        dispatch(app, [
            {'method': 'new_component', 'args': ['must-not-run']},
            {'method': 'para', 'args': ['bad name', float('nan')]},
        ])
    assert calls == []


def test_invalid_sweep_payload_is_rejected_before_earlier_geometry():
    from tpc_service.sessions.model_api import dispatch
    seen = []
    app = SimpleNamespace(new_component=lambda name: seen.append(name))
    with pytest.raises(Exception):
        dispatch(app, [{'method': 'new_component', 'args': ['never-created']},
                       {'method': 'configure_sweep', 'args': ['s', {'sigma': {
                           'mode': 'logarithmic', 'start': 0, 'stop': 10, 'samples': 3}}]}])
    assert not seen


def test_model_api_stage_deduplicates_different_request_ids(tmp_path):
    from tpc_service.sessions import SessionManager
    manager = SessionManager(str(tmp_path.resolve()), backend='fake')
    binding = manager.ensure('test-model-api', 'allocate')
    manager._launch = lambda *args, **kwargs: None
    p = params([{'method': 'new_component', 'args': ['one']}])
    first = manager.submit(binding['session_id'], binding['credential'], 'first', 'model_api', p)
    second = manager.submit(binding['session_id'], binding['credential'], 'retry', 'model_api', p)
    assert first['job_id'] == second['job_id']


@pytest.mark.parametrize('flag', [0, 2, False, '1'])
def test_nonexecuting_geometry_flag_rejected_before_earlier_calls(flag):
    from tpc_service.sessions.model_api import dispatch
    seen = []
    app = SimpleNamespace(new_component=lambda name: seen.append(name))
    with pytest.raises(Exception):
        dispatch(app, [{'method': 'new_component', 'args': ['never-created']},
                       {'method': 'translate', 'args': ['solid', [1, 0, 0]],
                        'kwargs': {'log_flag': flag}}])
    assert seen == []


def test_settings_receipt_remains_unverified_through_dispatch():
    from tpc_service.sessions.model_api import dispatch
    seen = []
    receipt = {'history_submitted': True, 'readback_verified': False, 'solver_verified': False}
    app = SimpleNamespace(configure_fd_frequency=lambda settings: seen.append(settings) or receipt)
    result = dispatch(app, [{'method': 'configure_fd_frequency', 'args': [{'output_samples': 10}]}])
    assert result['configuration_receipts'] == [
        {'call_index': 0, 'method': 'configure_fd_frequency', 'receipt': receipt}]
