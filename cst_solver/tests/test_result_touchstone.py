import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from cst_solver._result_core import Result


class Item:
    xlabel = 'Frequency (GHz)'

    def __init__(self, run_id, freq, values, reference):
        self.run_id = run_id
        self.freq = freq
        self.values = values
        self.reference = reference

    def get_xdata(self):
        return self.freq

    def get_ydata(self):
        return self.values

    def get_ref_imp_data(self):
        return self.reference


class Module:
    def __init__(self, *, missing=(), mismatched_run=None, reference=(50.0,)):
        self.missing = set(missing)
        self.mismatched_run = mismatched_run
        self.reference = reference
        self.freq = np.array([1.0, 2.0, 3.0])
        self.parameters = {1: {'width': 1.7}, 2: {'width': 1.9}, 3: {'width': 2.1}}

    def get_run_ids(self, path, skip_nonparametric=False):
        return [1, 2, 3] if skip_nonparametric else [0, 1, 2, 3]

    def get_parameter_combination(self, run_id):
        return self.parameters[run_id]

    def get_result_item(self, path, run_id=0, **kwargs):
        leaf = path.rsplit('\\', 1)[-1].replace(' ', '')
        if (run_id, leaf) in self.missing:
            raise KeyError(path)
        row, col = map(int, leaf[1:].split(','))
        values = np.full(3, (10 * row + col + run_id) / 100, dtype=complex)
        actual_id = self.mismatched_run if self.mismatched_run is not None else run_id
        return Item(actual_id, self.freq, values, self.reference)


def reader(module):
    out = Result.__new__(Result)
    out.result_module = module
    out.last_errors = {}
    return out


def test_exports_each_native_run_with_parameters_and_hashes(tmp_path):
    target = tmp_path / 'sweep'
    out = reader(Module()).export_touchstone_sweep(
        target, port_count=2, reference_ohm=50, frequency_unit='GHz',
        parameter_names=['width'])

    assert out['status'] == 'complete'
    assert [row['run_id'] for row in out['cases']] == [1, 2, 3]
    assert [row['parameters'] for row in out['cases']] == [
        {'width': 1.7}, {'width': 1.9}, {'width': 2.1}]
    for row in out['cases']:
        path = target / row['file']
        assert path.suffix == '.s2p'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
        lines = path.read_text().splitlines()
        assert lines[0] == '! CST Run ID: ' + str(row['run_id'])
        assert lines[2] == '# GHz S RI R 50'
        assert len(lines) == 6
    assert json.loads((target / 'manifest.json').read_text())['case_count'] == 3


def test_refuses_incomplete_matrix_without_creating_output(tmp_path):
    target = tmp_path / 'incomplete'
    module = Module(missing={(2, 'S2,1')})
    with pytest.raises(ValueError, match='S2,1'):
        reader(module).export_touchstone_sweep(
            target, port_count=2, reference_ohm=50, frequency_unit='GHz')
    assert not target.exists()


def test_refuses_run_fallback_and_missing_parameter_identity(tmp_path):
    with pytest.raises(ValueError, match='Run ID'):
        reader(Module(mismatched_run=8)).export_touchstone_sweep(
            tmp_path / 'wrong-id', port_count=2, reference_ohm=50,
            frequency_unit='GHz')
    module = Module()
    module.parameters[2] = {}
    with pytest.raises(ValueError, match='parameter'):
        reader(module).export_touchstone_sweep(
            tmp_path / 'missing-parameter', port_count=2,
            reference_ohm=50, frequency_unit='GHz',
            parameter_names=['width'])


def test_requires_new_output_directory_and_explicit_frequency_unit(tmp_path):
    target = tmp_path / 'existing'
    target.mkdir()
    with pytest.raises(FileExistsError):
        reader(Module()).export_touchstone_sweep(
            target, port_count=2, reference_ohm=50, frequency_unit='GHz')
    with pytest.raises(ValueError, match='frequency_unit'):
        reader(Module()).export_touchstone_sweep(
            tmp_path / 'no-unit', port_count=2, reference_ohm=50,
            frequency_unit='GHzx')


def test_manifest_preserves_complex_native_reference_impedance_as_json(tmp_path):
    out = reader(Module(reference=(50 + 2j,))).export_touchstone_sweep(
        tmp_path / 'complex-reference', port_count=2, reference_ohm=50,
        frequency_unit='GHz')
    assert out['cases'][0]['normalization']['native_reference_impedance'] == [
        {'real': 50.0, 'imag': 2.0}]
