"""Results/modeler path discovery and complex S versus adaptive mesh pass.

This mixin uses the Result instance's existing offline result module. The only
optional live object is a Model3D explicitly supplied by the caller; no session
is discovered, created, connected, modified or closed here.
"""
import re

import numpy as np

from cst_solver.failures import structured_error


# Keep the original path for reading. Parsing it does not create guessed paths.
_ADAPTIVE_S_PATH = re.compile(
    r'^1D Results\\Adaptive Meshing\\f=(?P<frequency>[^\\]+)'
    r'\\S-Parameters\\(?P<parameter>S\s*\d+(?:\(\d+\))?\s*,\s*\d+(?:\(\d+\))?)$')
_FREQUENCY = re.compile(
    r'^\s*(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)'
    r'\s*(?P<unit>Hz|kHz|MHz|GHz|THz)?\s*$')
_FREQUENCY_UNITS = ('Hz', 'kHz', 'MHz', 'GHz', 'THz')


def _validate_request(run_id, frequency_unit):
    if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id < 0:
        raise ValueError('run_id must be an explicit nonnegative integer')
    if frequency_unit is not None and frequency_unit not in _FREQUENCY_UNITS:
        raise ValueError('frequency_unit must be Hz, kHz, MHz, GHz, THz or None')


def _frequency_info(raw, frequency_unit):
    match = _FREQUENCY.fullmatch(raw)
    value = float(match['value']) if match else None
    path_unit = match['unit'] if match else None
    if value is not None and (not np.isfinite(value) or value < 0):
        raise ValueError('adaptation frequency must be finite and nonnegative')
    if path_unit and frequency_unit and path_unit != frequency_unit:
        raise ValueError('frequency_unit conflicts with the unit in the tree path')
    return dict(raw=raw, value=value, unit=path_unit or frequency_unit,
                source='tree_path', unit_source='tree_path' if path_unit else
                'caller' if frequency_unit else 'unknown')


def _normalization(item):
    """Preserve the native reference data, without inventing wave conventions."""
    report = dict(status='unknown', reference_impedance=None,
                  source='ResultItem.get_ref_imp_data', wave_definition='unknown',
                  renormalized=False, errors=[])
    try:
        reference = item.get_ref_imp_data()
        if reference is not None and np.size(reference):
            report.update(status='available', reference_impedance=reference)
    except Exception as exc:
        report['errors'].append(structured_error(
            'reference_impedance_unavailable', f'{type(exc).__name__}: {exc}'))
    return report


class AdaptiveResultsMixin:
    """Separate Pass-axis data from ordinary frequency-axis S-parameters."""

    def enumerate_result_paths(self, *, modeler=None):
        """Union exact paths, preserving provenance and per-source failures.

        ``modeler`` must be an already authorized Model3D for the same project.
        Only its get_tree_items() method is called; project identity is the
        caller's responsibility. A failed source never becomes an empty success.
        """
        items, errors = {}, []
        sources = dict(results='ok', modeler='not_requested')
        readers = [('results', self.result_module)]
        if modeler is not None:
            readers.append(('modeler', modeler))
        for source, reader in readers:
            try:
                for item in reader.get_tree_items():
                    path = item if isinstance(item, str) else getattr(item, 'treepath', None)
                    if not isinstance(path, str) or not path.strip():
                        raise ValueError('tree item has no nonempty string path')
                    if path not in items:
                        items[path] = dict(path=path, sources=[])
                    if source not in items[path]['sources']:
                        items[path]['sources'].append(source)
                sources[source] = 'ok'
            except Exception as exc:
                sources[source] = 'failed'
                errors.append(structured_error(
                    'result_tree_enumeration_failed', f'{type(exc).__name__}: {exc}',
                    source=source))
        return dict(items=list(items.values()), sources=sources, errors=errors,
                    complete=not errors)

    def read_adaptive_s_parameter(self, tree_path, *, run_id, frequency_unit=None):
        """Read one exact adaptive S path using an explicit run, without enumeration.

        xlabel must be Pass. Returns independent integer passes and complex S
        arrays, not the [frequency, S] table used by ordinary frequency curves.
        No interpolation, unit inference, renormalization or run fallback occurs.
        """
        _validate_request(run_id, frequency_unit)
        match = _ADAPTIVE_S_PATH.fullmatch(tree_path) if isinstance(tree_path, str) else None
        if not match:
            raise ValueError('expected a full Adaptive Meshing S-Parameters path')
        frequency = _frequency_info(match['frequency'], frequency_unit)
        item = self.get_result_item(tree_path, run_id=run_id, load_impedances=True)
        xlabel = getattr(item, 'xlabel', None)
        if not isinstance(xlabel, str) or xlabel.strip().casefold() != 'pass':
            raise ValueError(f'expected Pass axis, got {xlabel!r}')
        native_run_id = getattr(item, 'run_id', None)
        if run_id != 0 and native_run_id is not None and native_run_id != run_id:
            raise ValueError(f'native run_id={native_run_id!r} differs from requested run_id={run_id}')
        x = np.asarray(item.get_xdata(), dtype=complex)
        y = np.asarray(item.get_ydata(), dtype=complex)
        if (x.ndim != 1 or y.ndim != 1 or not x.size or x.size != y.size or
                not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)) or
                np.any(x.imag != 0)):
            raise ValueError('Pass/S arrays must be nonempty finite 1D arrays of equal length, with real Pass values')
        passes = x.real
        # Bound before casting so malformed native data cannot overflow int64.
        if (np.any(passes < 1) or np.any(passes >= 2**63) or
                np.any(passes != np.floor(passes)) or np.any(np.diff(passes) <= 0)):
            raise ValueError('Pass values must be strictly increasing positive integers')
        return dict(path=tree_path, sources=['caller'], run_id=run_id,
                    native_run_id=native_run_id, parameter=match['parameter'],
                    adaptation_frequency=frequency, axis='mesh_pass', xlabel=xlabel,
                    passes=passes.astype(np.int64), s_complex=y.copy(),
                    normalization=_normalization(item))

    def read_adaptive_s_parameters(self, *, run_id, modeler=None, frequency_unit=None):
        """Read discovered Pass curves; report errors and never claim a full matrix.

        ``complete`` only means all discovered candidates could be read and all
        requested sources enumerated. It is not a port/frequency coverage check.
        Normalization diagnostics remain on each curve even when S is readable.
        """
        _validate_request(run_id, frequency_unit)
        enumeration = self.enumerate_result_paths(modeler=modeler)
        curves, errors, candidates = [], list(enumeration['errors']), 0
        for entry in enumeration['items']:
            if not _ADAPTIVE_S_PATH.fullmatch(entry['path']):
                continue
            candidates += 1
            try:
                curve = self.read_adaptive_s_parameter(
                    entry['path'], run_id=run_id, frequency_unit=frequency_unit)
                curve['sources'] = list(entry['sources'])
                curves.append(curve)
            except Exception as exc:
                errors.append(structured_error(
                    'adaptive_s_read_failed', f'{type(exc).__name__}: {exc}',
                    path=entry['path'], sources=list(entry['sources']), run_id=run_id))
        status = ('partial' if curves else 'failed') if errors else 'ok' if candidates else 'not_found'
        return dict(curves=curves, enumeration=enumeration, errors=errors,
                    complete=not errors, status=status, run_id=run_id,
                    matrix_completeness='not_evaluated')
