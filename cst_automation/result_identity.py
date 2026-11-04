"""Select stored schematic identities from caller-supplied native observations."""
import math
import re
from collections.abc import Mapping


_ID = re.compile(r'^Schematic:RunID:([1-9][0-9]*)$')


def select_schematic_result_id(available_by_path, parameters_by_id, *, expected_parameters,
                               requested_id=None, rtol=1e-10, atol=1e-12):
    """Require common paths and actual stored parameters; never choose a largest ID.

    No native calls are made. Observations must come from the caller's target
    task and saved/native parameter combinations, not current UI parameters.
    A parameter match alone does not prove a result belongs to a new execution.
    """
    if not isinstance(available_by_path, Mapping) or not available_by_path:
        raise ValueError('Nonempty target path observations are required')
    if not isinstance(parameters_by_id, Mapping):
        raise ValueError('Stored parameter combinations are required')
    if not isinstance(expected_parameters, Mapping) or not expected_parameters:
        raise ValueError('Explicit expected parameters are required')
    for value in (rtol, atol):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError('Tolerances must be finite and nonnegative')
    def number(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Parameter values must be finite numeric observations')
        return value
    for name, value in expected_parameters.items():
        if not isinstance(name, str) or not name:
            raise ValueError('Parameter names must be nonempty strings')
        number(value)
    common = None
    for path, ids in available_by_path.items():
        if not isinstance(path, str) or not path or isinstance(ids, (str, bytes)):
            raise ValueError('Each target path must have an observed ID collection')
        positive = {value for value in ids if isinstance(value, str) and _ID.fullmatch(value)}
        common = positive if common is None else common & positive
    alias = requested_id is None or requested_id == '' or requested_id == 'Schematic:RunID:0'
    if not alias and (not isinstance(requested_id, str) or not _ID.fullmatch(requested_id) or requested_id not in common):
        raise ValueError('Requested positive schematic ID must exist on every target path')
    if alias:
        for rid in common:
            actual = parameters_by_id.get(rid)
            if not isinstance(actual, Mapping) or any(name not in actual for name in expected_parameters):
                raise ValueError('Unknown candidate parameters cannot prove a unique match')
            for name in expected_parameters:
                number(actual[name])
    def matches(result_id):
        actual = parameters_by_id.get(result_id)
        if not isinstance(actual, Mapping):
            return False
        try:
            return all(name in actual and math.isclose(number(actual[name]), expected,
                       rel_tol=rtol, abs_tol=atol) for name, expected in expected_parameters.items())
        except ValueError:
            return False
    candidates = [rid for rid in (common if alias else [requested_id]) if matches(rid)]
    if len(candidates) != 1:
        raise ValueError('Stored run parameters are missing, mismatched or ambiguous')
    rid = candidates[0]
    return {'result_id': rid, 'selection': 'unique_parameter_match' if alias else 'explicit_parameter_match',
            'tree_paths': list(available_by_path), 'parameters': dict(parameters_by_id[rid]),
            'solver_verified': False, 'execution_identity_verified': False}
