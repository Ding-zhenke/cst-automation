from types import SimpleNamespace
from cst_solver import setup as CstSetup
from cst_solver.modeling.curves_ops import CurveOpsMixin

def test_extrusion_keeps_exact_solid_name():
    app=CurveOpsMixin()
    code=app.extrude('profiles:p','p','t',log_flag=0)
    assert '.Name "p"' in code
    assert '.Name "p "' not in code

def test_rebuild_helpers_are_public():
    for name in ['new_curve','set_wcs_basis','activate_global_wcs','configure_fem_solver']:
        assert callable(getattr(CstSetup,name,None))


def test_parameter_sweep_helpers_do_not_use_unsupported_reset():
    from cst_solver.simulation.solver import SolverMixin
    app=SolverMixin();blocks=[]
    app.cst_file=SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda n,v:blocks.append(v)))
    app.add_parameter_sweep_sequence('cases')
    app.add_sweep_parameter_samples('cases','ka','-.4','.4',3)
    assert all('.Reset' not in b for b in blocks)
