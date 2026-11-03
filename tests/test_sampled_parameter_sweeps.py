"""API regression checks; no CST process or solver is started."""
from types import SimpleNamespace
import pytest
from cst_solver.simulation.solver import SolverMixin


def app_and_history():
    history=[]
    app=SolverMixin()
    app.cst_file=SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda name,code:history.append(code)))
    return app,history


def test_native_linear_and_logarithmic_sample_modes():
    app,history=app_and_history()
    app.add_sweep_parameter_samples('study','length',1,3,5)
    app.add_sweep_parameter_samples('study','conductivity',10,10000,4,logarithmic=True)
    assert '.AddParameter_Samples "study", "length", "1", "3", "5", "False"' in history[0]
    assert '.AddParameter_Samples "study", "conductivity", "10", "10000", "4", "True"' in history[1]
    assert all('.Start' not in code for code in history)


def test_mixed_sweep_preserves_native_modes_in_one_submission():
    app,history=app_and_history()
    app.configure_sweep('study',{
        'length':dict(mode='linear',start=1,stop=3,samples=5),
        'conductivity':dict(mode='logarithmic',start=10,stop=10000,samples=4),
        'state':[0,1],
    },replace_all=True)
    assert len(history)==1
    assert history[0].count('.AddParameter_Samples')==2
    assert history[0].count('.AddParameter_ArbitraryPoints')==1
    assert '.DeleteAllSequences' in history[0] and '.Start' not in history[0]


@pytest.mark.parametrize('axis',[
    dict(mode='logarithmic',start=0,stop=10,samples=3),
    dict(mode='logarithmic',start=-1,stop=10,samples=3),
    dict(mode='linear',start=1,stop=1,samples=3),
    dict(mode='linear',start=1,stop=3,samples=1),
    dict(mode='linear',start=1,stop=3,samples=True),
    dict(mode='linear',start=1,stop=float('inf'),samples=3),
    dict(mode='log',start=1,stop=10,samples=3),
    dict(mode='linear',start=1,stop=3,samples=3,typo=True),
])
def test_invalid_late_axis_does_not_partially_write(axis):
    app,history=app_and_history()
    with pytest.raises((ValueError,TypeError)):
        app.configure_sweep('study',{'valid':[1,2],'invalid':axis},replace_all=True)
    assert history==[]


def test_explicit_zero_can_be_combined_with_a_positive_log_axis():
    app,history=app_and_history()
    app.configure_sweep('off',{'conductivity':[0]})
    app.configure_sweep('on',{'conductivity':dict(mode='logarithmic',start=100,stop=100000,samples=4)})
    assert '.DeleteAllSequences' not in ''.join(history)
    assert '.AddParameter_ArbitraryPoints "off", "conductivity", "0"' in history[0]
    assert '"100", "100000", "4", "True"' in history[1]


def test_session_configure_sweep_accepts_ranges_before_queueing():
    from tpc_service.sessions.validation import validate
    p=dict(project_id='p',stage_id='s',sequence_name='study',parameters={
        'length':dict(mode='linear',start=1,stop=3,samples=5),
        'conductivity':dict(mode='logarithmic',start=10,stop=10000,samples=4)})
    validate('configure_sweep',p)
    p['parameters']['conductivity']['start']=0
    with pytest.raises(Exception):
        validate('configure_sweep',p)


@pytest.mark.parametrize('method,args',[
    ('cylinder',[[0,0],[1,0],[0,2],'via']),
    ('create_cylinder',[[0,0],[1,0],[0,2],'via']),
    ('create_brick',[0,1,0,1,0,1,'block']),
    ('create_sphere',[[0,0,0],1,'sphere']),
    ('create_cone',[1,0,2,'cone']),
    ('create_torus',[2,1,'torus']),
])
def test_existing_basic_shape_apis_are_routed_without_manual_history(method,args):
    from tpc_service.sessions.model_api import validate_calls
    validate_calls([dict(method=method,args=args)])
