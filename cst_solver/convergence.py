"""Evaluate supplied mesh evidence; no SDK access or refinement configuration."""
import copy
import math

__all__ = ['mesh_convergence_report']


def mesh_convergence_report(samples, *, target, expected_frequencies,
                            required_passes=1, max_passes=None,
                            computation_completed=None, warnings=()):
    """Delta S must be below target for consecutive passes at every frequency.

    Frequencies must use the same units/values as samples. Evidence must belong
    to one run and adaptation sequence; reset pass numbers are not merged.
    Unknown data is not a pass. Residuals and warnings remain raw evidence.
    """
    if not math.isfinite(target) or target <= 0:
        raise ValueError('target must be finite and positive')
    if isinstance(required_passes, bool) or not isinstance(required_passes, int) or required_passes < 1:
        raise ValueError('required_passes must be a positive integer')
    if max_passes is not None and (isinstance(max_passes, bool) or
            not isinstance(max_passes, int) or max_passes < 1):
        raise ValueError('max_passes must be a positive integer')
    if computation_completed is not None and not isinstance(computation_completed, bool):
        raise ValueError('computation_completed must be bool or None')
    frequencies = list(expected_frequencies)
    if not frequencies or any(not math.isfinite(f) for f in frequencies) or len(set(frequencies)) != len(frequencies):
        raise ValueError('expected_frequencies must be distinct finite values')
    rows, grouped = copy.deepcopy(list(samples)), {f: [] for f in frequencies}
    for row in rows:
        frequency, number, delta = row['frequency'], row['pass_number'], row.get('delta_s')
        if frequency not in grouped:
            raise ValueError('sample frequency was not declared')
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise ValueError('pass_number must be positive integer')
        if delta is not None and (not math.isfinite(delta) or delta < 0):
            raise ValueError('delta_s must be finite and nonnegative or None')
        grouped[frequency].append(row)
    reports = []
    for frequency, passes in grouped.items():
        passes.sort(key=lambda row: row['pass_number'])
        numbers = [row['pass_number'] for row in passes]
        if len(numbers) != len(set(numbers)):
            raise ValueError('duplicate frequency/pass observations')
        tail = passes[-required_passes:]
        complete = (len(tail) == required_passes and
                    all(row.get('delta_s') is not None for row in tail) and
                    all(b['pass_number'] == a['pass_number'] + 1 for a, b in zip(tail, tail[1:])))
        if passes and passes[-1].get('delta_s') is not None and passes[-1]['delta_s'] >= target:
            state = 'not_converged'
        elif complete:
            state = 'converged' if all(row['delta_s'] < target for row in tail) else 'not_converged'
        else:
            state = 'unknown'
        reports.append(dict(frequency=frequency, convergence=state,
                            max_passes_reached=bool(max_passes is not None and numbers and numbers[-1] >= max_passes)))
    states = [row['convergence'] for row in reports]
    state = ('not_converged' if 'not_converged' in states else
             'unknown' if 'unknown' in states else 'converged')
    return dict(computation_completed=computation_completed, convergence=state,
                validation_passed=computation_completed is True and state == 'converged',
                target=target, required_passes=required_passes, max_passes=max_passes,
                frequencies=reports, samples=rows, warnings=list(warnings))
