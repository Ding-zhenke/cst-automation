from types import SimpleNamespace
import pytest
from cst_solver.circuit.api import CircuitAPI
from cst_solver.circuit.adapter import CircuitError

class Obj:
    def __init__(self): self.xy=[50000,50000]; self.calls=[]
    def DoesExist(self): return True
    def GetPositionX(self): return self.xy[0]
    def GetPositionY(self): return self.xy[1]
    def Position(self,x,y): self.calls.append((x,y)); self.xy=[51000,52000]

@pytest.mark.parametrize('kind', ['Block','ExternalPort'])
def test_move_reads_actual_grid_position(kind):
    obj=Obj(); api=CircuitAPI(None,adapter=SimpleNamespace(select=lambda k,n: obj))
    result=api.set_position(kind,'existing',[51001,52001])
    assert obj.calls == [('51001','52001')]
    assert result['before']==[50000,50000] and result['readback']==[51000,52000]
    assert result['requested']==[51001,52001]

@pytest.mark.parametrize('position', [[0,1], [1,100000], [True,1], [float('nan'),1]])
def test_invalid_position_never_touches_adapter(position):
    api=CircuitAPI(None,adapter=SimpleNamespace(select=lambda *a: pytest.fail('native access')))
    with pytest.raises(CircuitError): api.set_position('Block','x',position)

def test_missing_object_not_modified():
    obj=Obj(); obj.DoesExist=lambda: False
    api=CircuitAPI(None,adapter=SimpleNamespace(select=lambda *a: obj))
    with pytest.raises(CircuitError): api.set_position('Block','x',[1,1])
    assert not obj.calls

def test_write_failure_preserves_partial_evidence():
    obj=Obj()
    def fail(*args): raise RuntimeError('native')
    obj.Position=fail
    api=CircuitAPI(None,adapter=SimpleNamespace(select=lambda *a: obj))
    with pytest.raises(CircuitError) as exc: api.set_position('Block','x',[1,1])
    assert exc.value.code == 'circuit_build_partial'
    assert exc.value.details['before'] == [50000,50000]
