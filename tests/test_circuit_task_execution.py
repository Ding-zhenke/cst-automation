import pytest
from types import SimpleNamespace
from cst_solver.circuit.task_execution import configure_task_execution
from cst_solver.circuit.adapter import CircuitError

class Task:
    def __init__(self): self.parallel='None'; self.options={'TD Voltages':'Off','TD Currents':'Off'}; self.calls=[]
    def Reset(self): pass
    def Name(self,name): self.name=name
    def DoesExist(self): return True
    def GetTypeForTask(self,name): return 'Transient'
    def GetProperty(self,k): return self.parallel
    def SetProperty(self,k,v): self.calls.append((k,v)); self.parallel=v
    def GetResultOption(self,k): return self.options[k]
    def SetResultOption(self,k,v): self.calls.append((k,v)); self.options[k]=v

def test_explicit_settings_and_native_readback():
    task=Task(); result=configure_task_execution(SimpleNamespace(SimulationTask=task),'SS','Transient',parallelization=8,
        result_options={'TD Voltages':'On (Parametric)','TD Currents':'On (Parametric)'})
    assert result['before']['parallelization']=='None'
    assert result['after']['parallelization']=='8'
    assert result['after']['result_options']['TD Voltages']=='On (Parametric)'
    assert not result['solver_verified']

@pytest.mark.parametrize('bad',[0,-1,True,'8','maximum',[]])
def test_invalid_parallelization_never_writes(bad):
    task=Task()
    with pytest.raises(CircuitError): configure_task_execution(SimpleNamespace(SimulationTask=task),'SS','Transient',parallelization=bad)
    assert not task.calls

def test_unknown_result_option_fails_before_any_write():
    task=Task()
    with pytest.raises(KeyError): configure_task_execution(SimpleNamespace(SimulationTask=task),'SS','Transient',parallelization='Maximum',result_options={'unknown':'On'})
    assert not task.calls

def test_partial_write_has_evidence():
    task=Task()
    def fail(k,v): raise RuntimeError('native failure')
    task.SetResultOption=fail
    with pytest.raises(CircuitError) as error:
        configure_task_execution(SimpleNamespace(SimulationTask=task),'SS','Transient',parallelization='Maximum',result_options={'TD Voltages':'On'})
    assert error.value.code=='circuit_build_partial' and error.value.details['completed']==['parallelization']

def test_wrong_type_refused():
    task=Task()
    with pytest.raises(CircuitError): configure_task_execution(SimpleNamespace(SimulationTask=task),'SS','Spectral Lines',parallelization='Maximum')
    assert not task.calls
