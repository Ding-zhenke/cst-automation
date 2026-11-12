import copy
from types import SimpleNamespace
import pytest
from cst_automation.workflow import digest
from cst_solver.circuit.adapter import CircuitError
from cst_solver.circuit.static_sp import remove_unconnected_self_em_block


def fake_adapter(tmp_path):
    project=tmp_path/'model.cst';project.write_bytes(b'project')
    blocks=[{'name':'self','type':'CST MICROWAVE STUDIO schematic block','files':[str(project)]},
            {'name':'network','type':'TOUCHSTONE block','files':[]}]
    class Net:
        def Reset(self): pass
        def GetNumberOfNets(self): return 1
        def GetNetNameByIndex(self,index): return 'n'
        def GetNumberOfSubnets(self,name): return 1
        def GetComponentPorts(self,name,index): return [['Block','network',0],['ExternalPort','P',0]]
    class Block:
        def __init__(self,name): self.name=name
        def DoesExist(self): return any(b['name']==self.name for b in blocks)
        def GetTypeName(self): return next(b['type'] for b in blocks if b['name']==self.name)
        def GetFile(self): return str(project)
        def Delete(self): blocks[:]=[b for b in blocks if b['name']!=self.name]
    class Adapter:
        app=SimpleNamespace(cst_file=SimpleNamespace(filename=lambda:str(project)))
        schematic=SimpleNamespace(Net=Net())
        def select(self,kind,name): return Block(name)
        def inspect(self): return copy.deepcopy({'blocks':blocks,'nets':[{'name':'n'}],
            'tasks':[{'name':'SP'}],'unknown':[],'parameters':{},'external_ports':[{'name':'P'}]})
    return Adapter()


def test_removes_only_reviewed_unconnected_self_block(tmp_path):
    adapter=fake_adapter(tmp_path); before=adapter.inspect()
    report=remove_unconnected_self_em_block(adapter,'self',expected_snapshot_digest=digest(before))
    assert [b['name'] for b in adapter.inspect()['blocks']]==['network']
    assert not report['geometry_verified'] and not report['solver_verified']


def test_connected_or_changed_self_block_is_refused_before_delete(tmp_path):
    adapter=fake_adapter(tmp_path); before=adapter.inspect()
    adapter.schematic.Net.GetComponentPorts=lambda name,index:[['Block','self',0],['ExternalPort','P',0]]
    with pytest.raises(ValueError): remove_unconnected_self_em_block(adapter,'self',expected_snapshot_digest=digest(before))
    assert adapter.select('Block','self').DoesExist()


def test_uncertain_delete_is_fenced(tmp_path):
    adapter=fake_adapter(tmp_path);before=adapter.inspect();original=adapter.select
    def select(kind,name):
        obj=original(kind,name)
        if name=='self': obj.Delete=lambda:(_ for _ in ()).throw(RuntimeError('native failure'))
        return obj
    adapter.select=select
    with pytest.raises(CircuitError) as exc:
        remove_unconnected_self_em_block(adapter,'self',expected_snapshot_digest=digest(before))
    assert exc.value.code=='circuit_build_partial'
