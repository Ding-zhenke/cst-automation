from types import SimpleNamespace

import pytest

from cst_automation.circuit_schema import validate_circuit_spec
from cst_solver.circuit.adapter import NativeAdapter
from cst_solver.circuit.api import CircuitAPI


class NativeCoordinatePort:
    """Coordinate fixture based on the observed CST setter/getter 50000 shift."""
    def Reset(self):
        pass

    def Name(self, value):
        self.name = value

    def Position(self, x, y):
        self.setter_position = (float(x), float(y))

    def Create(self):
        self.created = True

    def GetPositionX(self):
        return self.setter_position[0] - 50000

    def GetPositionY(self):
        return self.setter_position[1] - 50000


class NativeCoordinateBlock(NativeCoordinatePort):
    def DoesExist(self):
        return getattr(self, 'created', False)

    def Type(self, value):
        self.type_name = value

    def GetTypeName(self):
        return getattr(self, 'type_name', 'Resistor')


def test_native_position_survives_schema_and_is_converted_on_create():
    port = NativeCoordinatePort()
    adapter = object.__new__(NativeAdapter)
    adapter.schematic = SimpleNamespace(ExternalPort=port)
    spec = validate_circuit_spec({
        'schema_version': 1,
        'external_ports': [{'name': 'P1', 'native_position': [175, 300]}],
    })
    positions = adapter.apply(spec)
    assert port.setter_position == (50175, 50300)
    assert positions == [{
        'kind': 'ExternalPort', 'name': 'P1', 'coordinate_space': 'native',
        'requested': [175, 300], 'setter_position': [50175, 50300],
        'readback': [175, 300], 'readback_status': 'native_getter',
        'position_matches_request': True,
    }]


def test_native_position_survives_generic_block_creation():
    block = NativeCoordinateBlock()
    adapter = object.__new__(NativeAdapter)
    adapter.schematic = SimpleNamespace(Block=block)
    spec = {'units': {}, 'parameters': {}, 'resolved_si': {'parameters': {}}, 'em_links': [],
        'blocks': [{'name': 'R1', 'type': 'Resistor', 'native_position': [75, -24500],
                    'properties': {}, 'property_units': {}}],
        'external_ports': [], 'nets': [], 'probes': [], 'tasks': []}
    positions = adapter.apply(spec)
    assert block.setter_position == (50075, 25500)
    assert positions[0]['readback'] == [75, -24500]
    assert positions[0]['position_matches_request'] is True


def test_legacy_position_remains_a_direct_setter_frame_call():
    port = NativeCoordinatePort()
    adapter = object.__new__(NativeAdapter)
    adapter.schematic = SimpleNamespace(ExternalPort=port)
    spec = validate_circuit_spec({
        'schema_version': 1,
        'external_ports': [{'name': 'P1', 'position': [50175, 50300]}],
    })
    positions = adapter.apply(spec)
    assert port.setter_position == (50175, 50300)
    assert positions[0]['coordinate_space'] == 'cst'
    assert positions[0]['readback'] == [175, 300]
    assert positions[0]['position_matches_request'] is False


def test_native_position_rejects_ambiguous_or_out_of_frame_values():
    with pytest.raises(ValueError):
        validate_circuit_spec({'schema_version': 1, 'external_ports': [
            {'name': 'P1', 'position': [50175, 50300], 'native_position': [175, 300]},
        ]})
    with pytest.raises(ValueError):
        validate_circuit_spec({'schema_version': 1, 'external_ports': [
            {'name': 'P1', 'native_position': [50000, 0]},
        ]})


def test_configure_new_nonlinear_block_uses_native_position(tmp_path):
    block = NativeCoordinateBlock()
    schematic = SimpleNamespace(Block=block)
    adapter = object.__new__(NativeAdapter)
    adapter.schematic = schematic
    adapter.select = lambda kind, name: block
    adapter.properties = lambda *args, **kwargs: {}
    adapter.diode_readback = lambda name: {'properties': {'Model Type': 2}, 'property_metadata': {}}
    adapter.pins = lambda name: []
    api = CircuitAPI(None, adapter=adapter)
    report = api.configure_nonlinear_model(
        'D1', {'kind': 'berkeley_diode', 'native_position': [75, -24500]}, create=True)
    assert block.setter_position == (50075, 25500)
    assert report['position_readback']['readback'] == [75, -24500]
    assert report['position_readback']['position_matches_request'] is True
