from types import SimpleNamespace
from cst_solver import setup as CstSetup

def app():
    obj=object.__new__(CstSetup)
    history=[]
    obj.cst_file=SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda *args: history.append(args)))
    return obj,history

def test_two_point_rlc_uses_edge_element_and_explicit_coordinates():
    obj,h=app()
    obj.create_lumped_element(1,r="Rt",p1=["Lb","Cy","h+t"],p2=["Lb","Cy",0])
    code=h[0][1]
    assert "With LumpedElement" in code
    assert "LumpedFaceElement" not in code
    assert '.SetP1 "False", "Lb", "Cy", "h+t"' in code
    assert '.SetP2 "False", "Lb", "Cy", "0"' in code
    assert "UseProjection" not in code

def test_wave_port_keeps_symbolic_ranges_as_cst_expressions():
    obj,h=app()
    obj.create_waveguide_port_free(1,xrange=(0,0),yrange=("-Pw","Pw"),zrange=("-t","h+Ph"),orientation="xmin",port_on_bound=False,parameterized_ranges=True)
    code=h[0][1]
    assert '.Yrange "-Pw", "Pw"' in code
    assert '.Zrange "-t", "h+Ph"' in code
    assert '.Xrange 0, 0' in code
