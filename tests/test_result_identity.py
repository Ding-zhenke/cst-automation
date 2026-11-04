"""Synthetic run identities; no CST imports or project data."""
import pytest

from cst_automation.result_identity import select_schematic_result_id


def data():
    ids = ['Schematic:RunID:2', 'Schematic:RunID:7', 'Schematic:RunID:9']
    return {'Tasks\\HB\\V': ids, 'Tasks\\HB\\I': ids}, {
        ids[0]: {'tone': 3., 'side': 0.}, ids[1]: {'tone': 3., 'side': 1.},
        ids[2]: {'tone': 4., 'side': 0.}}


def test_alias_uses_parameters_and_not_largest_id():
    paths, params = data()
    out = select_schematic_result_id(paths, params, expected_parameters={'tone': 3., 'side': 0.},
                                     requested_id='Schematic:RunID:0')
    assert out['result_id'] == 'Schematic:RunID:2'
    assert out['selection'] == 'unique_parameter_match'
    assert out['solver_verified'] is False


@pytest.mark.parametrize('requested', ['Schematic:RunID:7', 'Schematic:RunID:8', '3D:RunID:2', 2, True])
def test_explicit_wrong_or_missing_identity_cannot_fall_back(requested):
    paths, params = data()
    with pytest.raises(ValueError):
        select_schematic_result_id(paths, params, expected_parameters={'tone': 3., 'side': 0.}, requested_id=requested)


@pytest.mark.parametrize('problem', ['missing_path', 'missing_parameter', 'ambiguous', 'nonfinite', 'empty_expected'])
def test_missing_or_ambiguous_identity_is_not_current_run(problem):
    paths, params = data(); expected = {'tone': 3., 'side': 0.}
    if problem == 'missing_path': paths['Tasks\\HB\\I'] = ['Schematic:RunID:7']
    if problem == 'missing_parameter': params['Schematic:RunID:2'].pop('side')
    if problem == 'ambiguous': params['Schematic:RunID:9'] = dict(params['Schematic:RunID:2'])
    if problem == 'nonfinite': params['Schematic:RunID:2']['tone'] = float('nan')
    if problem == 'empty_expected': expected = {}
    with pytest.raises(ValueError):
        select_schematic_result_id(paths, params, expected_parameters=expected)


def test_explicit_match_is_kept_even_with_another_matching_historical_run():
    paths, params = data(); params['Schematic:RunID:9'] = dict(params['Schematic:RunID:2'])
    out = select_schematic_result_id(paths, params, expected_parameters={'tone': 3., 'side': 0.},
                                    requested_id='Schematic:RunID:2')
    assert out['result_id'] == 'Schematic:RunID:2'
    assert out['selection'] == 'explicit_parameter_match'


def test_unknown_other_candidate_cannot_prove_unique_alias_match():
    paths, params = data(); params.pop('Schematic:RunID:9')
    with pytest.raises(ValueError):
        select_schematic_result_id(paths, params, expected_parameters={'tone': 3., 'side': 0.})


def test_native_wrapper_reads_common_ids_and_parameter_combinations_only():
    from types import SimpleNamespace
    from cst_solver.circuit.native import resolve_schematic_result_id
    paths, params = data(); reads = []
    schematic = SimpleNamespace(ResultTree=SimpleNamespace(GetResultIDsFromTreeItem=lambda path: paths[path]))
    def reader(rid):
        reads.append(rid)
        return params[rid]
    out = resolve_schematic_result_id(schematic, list(paths), read_parameters=reader,
                                      expected_parameters={'tone': 3., 'side': 0.})
    assert out['result_id'] == 'Schematic:RunID:2'
    assert set(reads) == set(params)
