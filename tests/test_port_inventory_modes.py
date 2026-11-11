from types import SimpleNamespace

import pytest

from cst_solver.simulation.port_replacement import port_inventory


@pytest.mark.parametrize('kind,modes,valid', [
    ('Discrete', 0, True), ('Discrete', 1, True), ('Waveguide', 1, True),
    ('Waveguide', 2, True), ('Waveguide', 0, False), ('Discrete', -1, False),
    ('Waveguide', -1, False), ('Discrete', True, False), ('Discrete', 0.0, False),
    ('Discrete', '0', False), ('Unknown', 0, False),
])
def test_native_modes_are_type_specific_and_not_normalized(kind, modes, valid):
    port = SimpleNamespace(StartPortNumberIteration=lambda: 1, GetNextPortNumber=lambda: 1,
                           GetType=lambda pid: kind, GetNumberOfModes=lambda pid: modes)
    app = SimpleNamespace(cst_file=SimpleNamespace(model3d=SimpleNamespace(Port=port)))
    if valid:
        assert port_inventory(app) == {'1': {'type': kind, 'number_of_modes': modes}}
    else:
        with pytest.raises(ValueError): port_inventory(app)
