import pytest

from cst_solver.circuit.adapter import CircuitError, attach_external_port_to_net


class Net:
    def __init__(self):
        self.nets = {'signal': {('Block', 'device', 0), ('Block', 'source', 1)},
                     'bias': {('Block', 'device', 1), ('Block', 'bias', 0)}}
        self.writes = 0

    def Reset(self):
        pass

    def GetNumberOfNets(self):
        return len(self.nets)

    def GetNetNameByIndex(self, index):
        return list(self.nets)[index]

    def GetComponentPorts(self, name, index):
        return list(self.nets[name])

    def GetNumberOfSubnets(self, name):
        return 1

    def GetNetName(self, endpoint):
        return next((name for name, members in self.nets.items() if tuple(endpoint) in members), '')

    def AddComponentPorts(self, name, endpoints, separate):
        self.writes += 1
        for endpoint in endpoints:
            self.nets[name].add(tuple(endpoint))
        return name

    def Apply(self):
        pass


def test_attaches_only_free_external_port_and_preserves_other_nets():
    net = Net()
    result = attach_external_port_to_net(net, 'signal', ('Externalport', 'rf', 0),
                                         [('Block', 'device', 0), ('Block', 'source', 1)])
    assert net.nets['signal'] == {('Block', 'device', 0), ('Block', 'source', 1), ('Externalport', 'rf', 0)}
    assert net.nets['bias'] == {('Block', 'device', 1), ('Block', 'bias', 0)}
    assert result['readback_verified'] is True


def test_refuses_connected_port_or_changed_original_before_write():
    net = Net()
    net.nets['bias'].add(('Externalport', 'rf', 0))
    with pytest.raises(CircuitError):
        attach_external_port_to_net(net, 'signal', ('Externalport', 'rf', 0),
                                    [('Block', 'device', 0), ('Block', 'source', 1)])
    assert net.writes == 0


def test_reports_partial_write_if_an_unrelated_net_changes():
    class CorruptingNet(Net):
        def Apply(self):
            self.nets['bias'].clear()

    net = CorruptingNet()
    with pytest.raises(CircuitError) as exc:
        attach_external_port_to_net(net, 'signal', ('Externalport', 'rf', 0),
                                    [('Block', 'device', 0), ('Block', 'source', 1)])
    assert exc.value.code == 'circuit_build_partial'
    net = Net()
    with pytest.raises(CircuitError):
        attach_external_port_to_net(net, 'signal', ('Externalport', 'rf', 0), [('Block', 'device', 0)])
    assert net.writes == 0
