from types import SimpleNamespace
import pytest
from cst_solver.circuit.static_sp import detach_source_endpoint, replace_probe_with_measurement_port
from cst_solver.circuit.adapter import CircuitError


class Net:
    def __init__(self):
        self.data = {'rf': {('Block', 'source', 0), ('Block', 'dut', 1), ('Block', 'load', 0)},
                     'other': {('Block', 'dut', 2), ('Block', 'bias', 0)}}
        self.writes = 0
    def Reset(self): pass
    def GetNumberOfNets(self): return len(self.data)
    def GetNetNameByIndex(self, i): return list(self.data)[i]
    def GetNumberOfSubnets(self, name): return 1
    def GetComponentPorts(self, name, i): return list(self.data[name])
    def RemoveComponentPorts(self, values, net):
        self.writes += 1
        for value in values: self.data[net].remove(tuple(value))
    def Apply(self): pass
    def AddComponentPorts(self, name, values, separate):
        self.writes += 1
        for value in values: self.data[name].add(tuple(value))
        return name


def adapter(net, kind='Voltage Signal Source'):
    return SimpleNamespace(schematic=SimpleNamespace(Net=net),
                           select=lambda kind_, name: SimpleNamespace(DoesExist=lambda: True, GetTypeName=lambda: kind))


def test_detach_checks_full_topology_and_keeps_other_nets():
    net = Net(); expected = [list(x) for x in net.data['rf']]
    result = detach_source_endpoint(adapter(net), 'rf', ['Block', 'source', 0], expected)
    assert result['readback_verified'] is True and result['solver_verified'] is False
    assert net.data['rf'] == {('Block', 'dut', 1), ('Block', 'load', 0)}
    assert net.data['other'] == {('Block', 'dut', 2), ('Block', 'bias', 0)}


@pytest.mark.parametrize('issue', ['membership', 'wrong_kind', 'insufficient'])
def test_invalid_or_unsafe_request_never_mutates(issue):
    net = Net()
    if issue == 'insufficient': net.data['rf'].remove(('Block', 'load', 0))
    expected = [list(x) for x in net.data['rf']]
    if issue == 'membership': expected.pop()
    with pytest.raises(ValueError):
        detach_source_endpoint(adapter(net, 'Diode' if issue == 'wrong_kind' else 'Voltage Signal Source'),
                               'rf', ['Block', 'source', 0], expected)
    assert net.writes == 0


def test_unrelated_mutation_is_partial_not_success():
    net = Net()
    def corrupt(): net.data['other'].clear()
    net.Apply = corrupt
    with pytest.raises(CircuitError) as exc:
        detach_source_endpoint(adapter(net), 'rf', ['Block', 'source', 0], [list(x) for x in net.data['rf']])
    assert exc.value.code == 'circuit_build_partial'


def test_two_member_net_replaces_probe_without_singleton():
    net = Net(); net.data['rf'] = {('Probe', 'probe', 1), ('Block', 'dut', 1)}
    seen = []
    net.Apply = lambda: seen.append(len(net.data['rf']))
    report = replace_probe_with_measurement_port(adapter(net), 'rf', ['Probe', 'probe', 1],
        ['ExternalPort', 'measure', 0], [list(x) for x in net.data['rf']])
    assert seen == [3, 2]
    assert net.data['rf'] == {('ExternalPort', 'measure', 0), ('Block', 'dut', 1)}
    assert report['readback_verified'] is True
