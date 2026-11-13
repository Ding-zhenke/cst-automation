"""Bounded circuit task settings; no creation, save, validation or solve."""
from .adapter import CircuitError


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 256 and not any(c in value for c in '\r\n\x00')


def normalize(task_name, expected_type, parallelization=None, result_options=None):
    if (not _text(task_name) or expected_type not in ('Transient', 'Spectral Lines')
            or (parallelization is None and result_options is None)):
        raise CircuitError('circuit_spec_invalid', 'Existing circuit task and explicit settings required')
    if parallelization is not None:
        if type(parallelization) is int and parallelization > 0:
            parallelization = str(parallelization)
        elif parallelization not in ('Maximum', 'None') or not isinstance(parallelization, str):
            raise CircuitError('circuit_spec_invalid', 'Parallelization requires Maximum, None, or positive integer')
    if result_options is not None and (not isinstance(result_options, dict) or not result_options
            or len(result_options) > 128 or any(not _text(k) or not _text(v) for k,v in result_options.items())):
        raise CircuitError('circuit_spec_invalid', 'Result options require bounded explicit native names and values')
    return task_name, expected_type, parallelization, result_options or {}


def configure_task_execution(schematic, task_name, expected_type, *, parallelization=None, result_options=None):
    task_name, expected_type, parallelization, options = normalize(task_name, expected_type, parallelization, result_options)
    task=schematic.SimulationTask
    task.Reset(); task.Name(task_name)
    if not task.DoesExist() or str(task.GetTypeForTask(task_name)).casefold() != expected_type.casefold():
        raise CircuitError('circuit_topology_invalid', 'Existing task type differs')
    # Read all requested keys before writing; unsupported names fail before mutation.
    before={'parallelization': str(task.GetProperty('parallelization')) if parallelization is not None else None,
            'result_options': {k: str(task.GetResultOption(k)) for k in options}}
    completed=[]; stage='write'
    try:
        if parallelization is not None:
            task.SetProperty('parallelization', parallelization); completed.append('parallelization')
        for key,value in options.items():
            task.SetResultOption(key,value); completed.append(key)
        stage='readback'
        after={'parallelization': str(task.GetProperty('parallelization')) if parallelization is not None else None,
               'result_options': {k: str(task.GetResultOption(k)) for k in options}}
        if (parallelization is not None and after['parallelization'] != parallelization) or after['result_options'] != options:
            raise ValueError('Native task settings readback differs')
    except Exception as exc:
        raise CircuitError('circuit_build_partial', 'Task settings write/readback failed',
                           stage=stage, completed=completed, before=before,
                           original_type=type(exc).__name__, original_message=str(exc)) from exc
    return {'task_name':task_name, 'task_type':expected_type, 'before':before, 'after':after,
            'solver_verified':False}
