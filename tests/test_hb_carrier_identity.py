"""Regression for reused parameter-state IDs and spectrum/parameter mismatch."""
from types import SimpleNamespace

import pytest

from cst_solver.circuit.native import resolve_hb_carriers


LEFT = r'Tasks\Sweep\HB\Voltage\left'
RIGHT = r'Tasks\Sweep\HB\Current\right'
OLD = 'Schematic:RunID:123'
NEWER = 'Schematic:RunID:200'


def fixture():
    parameters = {OLD: {'rf': 140.0, 'direction': 0.0},
                  NEWER: {'rf': 150.0, 'direction': 0.0}}
    spectra = {OLD: {'x': [0., 140., 145.], 'yre': [0., 1., 2.], 'yim': [0., 3., 4.]},
               NEWER: {'x': [0., 150.], 'yre': [0., 2.], 'yim': [0., 1.]}}
    reads = []
    def result(path, rid):
        reads.append((path, rid))
        return SimpleNamespace(GetArray=spectra[rid].__getitem__)
    tree = SimpleNamespace(GetResultIDsFromTreeItem=lambda _: [OLD, NEWER], GetResultFromTreeItem=result)
    schematic = SimpleNamespace(ResultTree=tree)
    def resolve(**kwargs):
        return resolve_hb_carriers(schematic, [LEFT, RIGHT], read_parameters=parameters.__getitem__,
            expected_parameters={'rf': 140., 'direction': 0.}, frequency_parameter='rf',
            carrier_frequency=140., **kwargs)
    return resolve, parameters, spectra, reads


def test_reused_older_id_is_selected_by_frequency_and_direction():
    resolve, parameters, spectra, reads = fixture()
    result = resolve(requested_id='Schematic:RunID:0')
    assert result['result_id'] == OLD and result['carriers'][LEFT] == 1 + 3j
    assert reads == [(LEFT, OLD), (RIGHT, OLD)]
    assert result['execution_identity_verified'] is result['solver_verified'] is False


def test_wrong_explicit_id_never_falls_back():
    resolve, parameters, spectra, reads = fixture()
    with pytest.raises(ValueError): resolve(requested_id=NEWER)
    assert reads == []


@pytest.mark.parametrize('axis', [[0., 139.], [0., 140., 140.]])
def test_wrong_or_ambiguous_carrier_fails_without_other_run_fallback(axis):
    resolve, parameters, spectra, reads = fixture()
    spectra[OLD] = {'x': axis, 'yre': [0.] * len(axis), 'yim': [0.] * len(axis)}
    with pytest.raises(ValueError, match='Carrier validation failed'):
        resolve(requested_id=OLD)
    assert reads == [(LEFT, OLD)]


def test_expected_frequency_must_agree_with_carrier():
    resolve, parameters, spectra, reads = fixture()
    parameters[OLD]['rf'] = 140.000001
    # Explicitly loosen parameter matching only; carrier tolerance remains strict.
    with pytest.raises(ValueError, match='differs'):
        resolve(requested_id=OLD, parameter_atol=0.001)
    assert reads == []
