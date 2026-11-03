"""Strict nonlinear readback boundary; no solver emulation."""
from types import SimpleNamespace

import pytest

from cst_solver.circuit.adapter import NativeAdapter, CircuitError


SCHEMA = [
    ('Initial State', 'integer', '1', ''),
    ('Relative Device Area', 'double', '1', ''),
    ('Temperature', 'double', '27', 'degC'),
    ('Nominal temperature', 'double', '27', 'degC'),
    ('Saturation current temperature exponent', 'double', '3', ''),
    ('Saturation current', 'double', '1e-14', 'A'),
    ('Emission coefficient', 'double', '1', ''),
    ('Reverse breakdown voltage', 'double', '1e12', 'V'),
    ('Current at breakdown voltage', 'double', '1e-10', 'A'),
    ('Idealty factor for reverse breakdown', 'double', '1', ''),
    ('Zero-bias depletion capacitance', 'double', '0', 'pF'),
    ('Built-in junction potential', 'double', '1', 'V'),
    ('Junction grading coefficient', 'double', '.5', ''),
    ('Transit time', 'double', '0', 'ns'),
    ('Series resistance', 'double', '1', 'Ohm'),
]


class Block:
    def __init__(self, rows=SCHEMA): self.rows = list(rows); self.writes = []
    def Reset(self): pass
    def Name(self, name): pass
    def GetTypeName(self): return 'Diode'
    def StartPropertyIteration(self): self.it = iter(self.rows)
    def GetNextProperty(self): return next(self.it, ('', '', '', ''))[:3]
    def GetUnitForProperty(self, key): return next(r[3] for r in self.rows if r[0] == key)
    def SetIntegerProperty(self, key, value): self.writes.append((key, value))
    def GetProperty(self, key):
        assert key != 'Model Type', 'No generic Model Type getter exists'
        return next(r[2] for r in self.rows if r[0] == key)


def adapter(block):
    return NativeAdapter(SimpleNamespace(cst_file=SimpleNamespace(schematic=SimpleNamespace(Block=block))))


def test_model_switch_has_annotated_native_schema_identity_and_no_fake_enum_readback():
    block = Block()
    actual = adapter(block).properties('D1', {'Model Type': 2}, {})
    assert block.writes == [('Model Type', '2')]
    assert actual['Model Type'] == {'requested_enum': 2, 'model_identity': {
        'name': 'Berkeley SPICE', 'evidence': 'documented_native_property_schema'}}


def test_model_selector_is_applied_first_even_when_requested_last():
    block = Block()
    def switch(key, value):
        block.writes.append((key, value))
        block.rows = [r if r[0] != 'Series resistance' else (*r[:2], '0', r[3]) for r in block.rows]
    def number(key, value):
        block.writes.append((key, value))
        block.rows = [r if r[0] != key else (*r[:2], value, r[3]) for r in block.rows]
    block.SetIntegerProperty = switch
    block.SetDoubleProperty = number
    block.SetLocalUnitForProperty = lambda *a: None
    actual = adapter(block).properties('D1', {'Series resistance': 1., 'Model Type': 2}, {'Series resistance': 'Ohm'})
    assert block.writes[0] == ('Model Type', '2')
    assert actual['Series resistance'] == '1'
    assert block.GetProperty('Series resistance') == '1'


def test_diode_readback_keeps_all_actual_values_types_and_units():
    actual = adapter(Block()).diode_readback('D1')
    assert actual['properties']['Series resistance'] == '1'
    assert len(actual['properties']) == 15
    assert actual['property_metadata']['Temperature'] == {'type': 'double', 'unit': 'degC'}
    assert actual['property_metadata']['Emission coefficient']['unit'] == ''


@pytest.mark.parametrize('rows', [SCHEMA[:-1], SCHEMA + [('extra', 'double', '0', '')],
    SCHEMA + [SCHEMA[0]], [('Initial State', 'double', '1', '')] + SCHEMA[1:]])
def test_missing_extra_duplicate_or_wrong_typed_model_cannot_be_verified(rows):
    with pytest.raises(CircuitError): adapter(Block(rows)).diode_readback('D1')
    with pytest.raises(CircuitError): adapter(Block(rows)).properties('D1', {'Model Type': 2}, {})


def test_unit_read_failure_is_not_dimensionless():
    block = Block()
    block.GetUnitForProperty = lambda key: (_ for _ in ()).throw(RuntimeError('unreadable'))
    with pytest.raises(RuntimeError, match='unreadable'): adapter(block).diode_readback('D1')


def test_unterminated_native_property_iterator_fails():
    block = Block()
    block.GetNextProperty = lambda: ('Same', 'double', '1')
    block.GetUnitForProperty = lambda key: ''
    with pytest.raises(CircuitError): adapter(block).diode_readback('D1')


def test_none_is_not_the_calibrated_native_end_sentinel():
    block = Block()
    native_next = block.GetNextProperty
    block.GetNextProperty = lambda: (lambda row: None if row == ('', '', '') else row)(native_next())
    with pytest.raises(CircuitError): adapter(block).diode_readback('D1')


def test_other_model_enum_is_rejected_before_mutation():
    block = Block()
    with pytest.raises(CircuitError): adapter(block).properties('D1', {'Model Type': 1}, {})
    assert not block.writes


def test_explicit_dimensionless_quantity_checks_native_unit_without_setting_one():
    block = Block()
    block.SetLocalUnitForProperty = lambda *a: pytest.fail('CST has no local unit for dimensionless diode parameters')
    block.SetDoubleProperty = lambda key, value: block.writes.append((key, value))
    actual = adapter(block).properties('D1', {'Emission coefficient': 1.}, {'Emission coefficient': '1'})
    assert actual['Emission coefficient'] == '1'
    block.GetUnitForProperty = lambda key: 'A'
    with pytest.raises(CircuitError): adapter(block).properties('D1', {'Emission coefficient': 1.}, {'Emission coefficient': '1'})


def inspection_adapter(block):
    block.StartBlockNameIteration = lambda: setattr(block, 'names', iter(['D1']))
    block.GetNextBlockName = lambda: next(block.names, '')
    block.GetFile = lambda: ''
    native = adapter(block)
    native.pins = lambda name: []
    native.schematic.Units = SimpleNamespace(GetUnit=lambda dim: 'test')
    native.schematic.ExternalPort = SimpleNamespace(StartPortNameIteration=lambda: None, GetNextPortName=lambda: '')
    native.schematic.Net = SimpleNamespace(Reset=lambda: None, GetNumberOfNets=lambda: 0)
    native.schematic.CircuitProbe = SimpleNamespace(StartProbeNameIteration=lambda: None, GetNextProbeName=lambda: '')
    native.schematic.SimulationTask = SimpleNamespace(StartTaskNameIteration=lambda: None, GetNextTaskName=lambda: '')
    native.schematic.GetNumberOfParameters = lambda: 0
    return native


@pytest.mark.parametrize('supported', [True, False])
def test_inspect_records_model_or_unknown_that_blocks_execution(supported):
    from cst_solver.circuit.evidence import configuration_complete
    block = Block(SCHEMA if supported else SCHEMA[:-1])
    native = inspection_adapter(block)
    actual = native.inspect()
    assert configuration_complete(actual) is supported
    if supported:
        assert actual['blocks'][0]['properties']['Series resistance'] == '1'
        assert actual['blocks'][0]['model_identity']['name'] == 'Berkeley SPICE'
    else:
        assert any(u['field'] == 'D1.diode_model' for u in actual['unknown'])


@pytest.mark.parametrize('model', ['KNOWN_DIODE', '', None])
def test_spice_model_identity_is_native_and_missing_identity_blocks_execution(model):
    from cst_solver.circuit.evidence import configuration_complete
    block = Block([])
    block.GetTypeName = lambda: 'SPICE file block'
    block.GetSpiceModel = lambda: model
    block.GetSpiceFilter = lambda: 'Berkeley SPICE'
    native = inspection_adapter(block)
    block.GetFile = lambda: 'model.cir'
    actual = native.inspect()
    assert configuration_complete(actual) is (model == 'KNOWN_DIODE')
    if model:
        assert actual['blocks'][0]['spice_model'] == model
        assert actual['blocks'][0]['spice_filter'] == 'Berkeley SPICE'
        assert actual['blocks'][0]['property_metadata'] == {}


def test_inline_spice_without_readable_netlist_is_unknown():
    from cst_solver.circuit.evidence import configuration_complete
    block = Block([])
    block.GetTypeName = lambda: 'SPICE block'
    block.GetSpiceModel = lambda: 'KNOWN_DIODE'
    block.GetSpiceFilter = lambda: 'AUTOMATIC'
    actual = inspection_adapter(block).inspect()
    assert not configuration_complete(actual)
    assert any(u['field']=='D1.spice_model' for u in actual['unknown'])
