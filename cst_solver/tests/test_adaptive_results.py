"""Injected readers only: these tests must never load/connect the CST SDK."""
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from cst_solver import Result, _result_core


MAIN = r'1D Results\S-Parameters\S1,1'
PASS = r'1D Results\Adaptive Meshing\f=5\S-Parameters\S1,1'
OTHER = r'1D Results\Adaptive Meshing\f=8\S-Parameters\S2,1'


class Item:
    xlabel = 'Pass'
    run_id = 7

    def __init__(self, x=(1, 2, 3), y=(.1 + .2j, .11 + .19j, .12 + .18j), impedance=75 + 2j):
        self.x, self.y, self.impedance = x, y, impedance

    def get_xdata(self):
        return self.x

    def get_ydata(self):
        return self.y

    def get_ref_imp_data(self):
        return self.impedance


@pytest.fixture(autouse=True)
def no_sdk(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('implicit SDK load or CST connection')
    monkeypatch.setattr(_result_core, '_load_cst_module', forbidden)
    import cst_solver
    monkeypatch.setattr(cst_solver, '_load_cst_module', forbidden)
    monkeypatch.setattr(cst_solver, 'setup', forbidden)


def reader(paths=(), items=None):
    r = Result.__new__(Result)
    r.last_errors = {}
    items = {PASS: Item()} if items is None else items
    def get(path, run_id, **kwargs):
        if run_id != 7:
            raise ValueError('run missing')
        return items[path]
    r.result_module = SimpleNamespace(get_tree_items=Mock(return_value=list(paths)),
                                      get_result_item=Mock(side_effect=get))
    return r


def test_union_preserves_exact_paths_and_both_sources_without_loading_sdk():
    r = reader([MAIN, SimpleNamespace(treepath=PASS), PASS])
    modeler = SimpleNamespace(get_tree_items=Mock(return_value=[PASS, OTHER]))
    report = r.enumerate_result_paths(modeler=modeler)
    assert report['items'] == [dict(path=MAIN, sources=['results']),
                               dict(path=PASS, sources=['results', 'modeler']),
                               dict(path=OTHER, sources=['modeler'])]
    assert report['complete'] and report['errors'] == []
    modeler.get_tree_items.assert_called_once_with()
    r.result_module.get_result_item.assert_not_called()


def test_default_enumeration_is_results_only():
    r = reader([MAIN])
    report = r.enumerate_result_paths()
    assert report['sources'] == {'results': 'ok', 'modeler': 'not_requested'}
    assert report['items'] == [dict(path=MAIN, sources=['results'])]


@pytest.mark.parametrize('broken_source', ['results', 'modeler'])
def test_enumeration_failure_is_explicit_and_retains_other_source(broken_source):
    r = reader([MAIN])
    modeler = SimpleNamespace(get_tree_items=Mock(return_value=[PASS]))
    target = r.result_module if broken_source == 'results' else modeler
    target.get_tree_items.side_effect = OSError('tree inaccessible')
    report = r.enumerate_result_paths(modeler=modeler)
    assert not report['complete']
    assert report['sources'][broken_source] == 'failed'
    assert report['errors'][0]['details']['source'] == broken_source
    assert report['items'][0]['path'] == (PASS if broken_source == 'results' else MAIN)


def test_read_modeler_only_paths_in_one_run_retains_pass_axis_and_complex_values():
    r = reader([MAIN])
    modeler = SimpleNamespace(get_tree_items=Mock(return_value=[PASS]))
    report = r.read_adaptive_s_parameters(run_id=7, modeler=modeler, frequency_unit='GHz')
    assert report['status'] == 'ok' and report['complete']
    assert report['matrix_completeness'] == 'not_evaluated'
    curve, = report['curves']
    assert curve['path'] == PASS and curve['sources'] == ['modeler']
    assert curve['run_id'] == curve['native_run_id'] == 7
    assert curve['axis'] == 'mesh_pass' and curve['xlabel'] == 'Pass'
    np.testing.assert_array_equal(curve['passes'], [1, 2, 3])
    np.testing.assert_allclose(curve['s_complex'], [.1+.2j, .11+.19j, .12+.18j])
    assert curve['passes'].dtype.kind in 'iu' and curve['s_complex'].dtype.kind == 'c'
    assert curve['adaptation_frequency'] == dict(raw='5', value=5.0, unit='GHz',
                                                source='tree_path', unit_source='caller')
    assert curve['normalization']['reference_impedance'] == 75 + 2j
    assert curve['normalization']['source'] == 'ResultItem.get_ref_imp_data'
    assert curve['normalization']['wave_definition'] == 'unknown'
    assert curve['normalization']['renormalized'] is False
    r.result_module.get_result_item.assert_called_once_with(PASS, 7, load_impedances=True)


def test_single_known_path_is_readable_without_any_tree_enumeration():
    r = reader()
    r.result_module.get_tree_items.side_effect = AssertionError('must not enumerate')
    curve = r.read_adaptive_s_parameter(PASS, run_id=7)
    assert curve['sources'] == ['caller']
    assert curve['adaptation_frequency']['unit'] is None
    assert curve['adaptation_frequency']['unit_source'] == 'unknown'
    r.result_module.get_tree_items.assert_not_called()


def test_native_reference_impedance_array_is_preserved_without_assuming_50_ohm():
    impedances = np.array([75+2j, 76+3j, 77+4j])
    curve = reader(items={PASS: Item(impedance=impedances)}).read_adaptive_s_parameter(PASS, run_id=7)
    np.testing.assert_array_equal(curve['normalization']['reference_impedance'], impedances)
    assert curve['normalization']['status'] == 'available'


@pytest.mark.parametrize('impedance', [None, []])
def test_missing_normalization_stays_unknown(impedance):
    curve = reader(items={PASS: Item(impedance=impedance)}).read_adaptive_s_parameter(PASS, run_id=7)
    assert curve['normalization']['status'] == 'unknown'
    assert curve['normalization']['reference_impedance'] is None


def test_normalization_read_failure_retains_data_and_error():
    item = Item()
    item.get_ref_imp_data = Mock(side_effect=OSError('impedance unavailable'))
    curve = reader(items={PASS: item}).read_adaptive_s_parameter(PASS, run_id=7)
    assert curve['normalization']['status'] == 'unknown'
    assert 'impedance unavailable' in str(curve['normalization']['errors'])
    assert len(curve['s_complex']) == 3


@pytest.mark.parametrize('label', ['Frequency / GHz', '', None])
def test_frequency_or_unknown_axis_is_rejected(label):
    item = Item()
    item.xlabel = label
    with pytest.raises(ValueError, match='Pass'):
        reader(items={PASS: item}).read_adaptive_s_parameter(PASS, run_id=7)


@pytest.mark.parametrize('x,y', [([1, 1], [1j, 2j]), ([2, 1], [1j, 2j]),
                                ([1, 2.5], [1j, 2j]), ([0, 1], [1j, 2j]),
                                ([1+1j], [1j]), ([float('nan')], [1j]),
                                ([], []), ([1, 2], [1j]), ([1], [complex('nan')])])
def test_invalid_pass_data_fails_without_truncation_or_filling(x, y):
    with pytest.raises(ValueError):
        reader(items={PASS: Item(x=x, y=y)}).read_adaptive_s_parameter(PASS, run_id=7)


def test_missing_passes_are_preserved_not_interpolated():
    curve = reader(items={PASS: Item(x=[2, 4], y=[1j, 2j])}).read_adaptive_s_parameter(PASS, run_id=7)
    np.testing.assert_array_equal(curve['passes'], [2, 4])


def test_run_id_is_required_and_missing_run_does_not_fallback():
    r = reader()
    with pytest.raises(TypeError):
        r.read_adaptive_s_parameter(PASS)
    with pytest.raises(RuntimeError, match='run missing'):
        r.read_adaptive_s_parameter(PASS, run_id=12)
    r.result_module.get_result_item.assert_called_once_with(PASS, 12, load_impedances=True)


def test_returned_native_run_must_match_requested_run():
    item = Item()
    item.run_id = 8
    with pytest.raises(ValueError, match='run'):
        reader(items={PASS: item}).read_adaptive_s_parameter(PASS, run_id=7)


def test_ordinary_and_pass_paths_are_never_mixed():
    r = reader([PASS, OTHER, MAIN])
    assert r.list_s_parameters() == ['S1,1']
    only_pass = reader([OTHER])
    assert only_pass.list_s_parameters() == []
    with pytest.raises(ValueError):
        r.read_adaptive_s_parameter(MAIN, run_id=7)
    r.result_module.get_result_item.assert_not_called()


def test_batch_partial_failures_keep_per_path_evidence():
    r = reader([PASS, OTHER], {PASS: Item()})
    report = r.read_adaptive_s_parameters(run_id=7)
    assert not report['complete'] and report['status'] == 'partial'
    assert len(report['curves']) == 1
    assert report['errors'][0]['details']['path'] == OTHER
    assert report['errors'][0]['details']['run_id'] == 7


def test_empty_enumeration_is_not_a_complete_matrix_claim():
    report = reader().read_adaptive_s_parameters(run_id=7)
    assert report['curves'] == [] and report['status'] == 'not_found'
    assert report['matrix_completeness'] == 'not_evaluated'


def test_partial_enumeration_reads_known_paths_but_never_reports_complete():
    r = reader([], {PASS: Item()})
    r.result_module.get_tree_items.side_effect = OSError('results enumeration unavailable')
    modeler = SimpleNamespace(get_tree_items=Mock(return_value=[PASS]))
    report = r.read_adaptive_s_parameters(run_id=7, modeler=modeler)
    assert len(report['curves']) == 1 and report['status'] == 'partial'
    assert not report['complete']
    assert report['errors'][0]['details']['source'] == 'results'


def test_failed_enumeration_is_not_not_found():
    r = reader()
    r.result_module.get_tree_items.side_effect = OSError('no access')
    report = r.read_adaptive_s_parameters(run_id=7)
    assert report['status'] == 'failed' and not report['complete']


def test_generator_failure_retains_already_enumerated_paths():
    def paths():
        yield PASS
        raise OSError('enumeration interrupted')
    r = reader()
    r.result_module.get_tree_items.return_value = paths()
    report = r.enumerate_result_paths()
    assert report['items'] == [dict(path=PASS, sources=['results'])]
    assert not report['complete']


def test_bad_modeler_is_reported_without_searching_for_a_session():
    report = reader([PASS]).enumerate_result_paths(modeler=object())
    assert report['sources']['modeler'] == 'failed'
    assert report['items'] == [dict(path=PASS, sources=['results'])]


@pytest.mark.parametrize('token,value,unit,unit_source', [
    ('1.25e1', 12.5, None, 'unknown'),
    ('8 GHz', 8.0, 'GHz', 'tree_path'),
    ('design_frequency', None, None, 'unknown'),
])
def test_frequency_token_and_units_are_preserved(token, value, unit, unit_source):
    path = PASS.replace('f=5', 'f=' + token)
    curve = reader(items={path: Item()}).read_adaptive_s_parameter(path, run_id=7)
    assert curve['adaptation_frequency'] == dict(raw=token, value=value, unit=unit,
                                                source='tree_path', unit_source=unit_source)


def test_conflicting_frequency_unit_is_not_silently_relabelled():
    path = PASS.replace('f=5', 'f=5 GHz')
    r = reader(items={path: Item()})
    with pytest.raises(ValueError, match='conflicts'):
        r.read_adaptive_s_parameter(path, run_id=7, frequency_unit='MHz')
    r.result_module.get_result_item.assert_not_called()


@pytest.mark.parametrize('run_id', [True, -1, 1.5, '7', None])
def test_invalid_run_is_rejected_before_reading_or_enumerating(run_id):
    r = reader([PASS])
    with pytest.raises(ValueError):
        r.read_adaptive_s_parameters(run_id=run_id)
    r.result_module.get_tree_items.assert_not_called()
    r.result_module.get_result_item.assert_not_called()


def test_explicit_zero_run_alias_preserves_requested_and_resolved_native_run():
    r = reader()
    r.result_module.get_result_item.side_effect = None
    r.result_module.get_result_item.return_value = Item()
    curve = r.read_adaptive_s_parameter(PASS, run_id=0)
    assert curve['run_id'] == 0 and curve['native_run_id'] == 7


def test_multimode_adaptive_name_is_preserved_as_native_parameter():
    path = PASS.replace('S1,1', 'S1(2),3(1)')
    curve = reader(items={path: Item()}).read_adaptive_s_parameter(path, run_id=7)
    assert curve['parameter'] == 'S1(2),3(1)'


def test_pass_only_tree_does_not_feed_frequency_bulk_reader():
    r = reader([PASS, OTHER])
    assert r.read_all_s_parameters() == {}
    r.result_module.get_result_item.assert_not_called()


def test_missing_native_run_metadata_remains_unknown():
    item = Item()
    item.run_id = None
    curve = reader(items={PASS: item}).read_adaptive_s_parameter(PASS, run_id=7)
    assert curve['run_id'] == 7 and curve['native_run_id'] is None
