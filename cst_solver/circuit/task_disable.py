"""Existing-task configuration only; no save, result readers or execution calls."""
from cst_automation.task_disable import normalize, OPERATION
from .adapter import CircuitError


def disable_tasks(schematic, tasks, *, confirm_idle, review_note):
    targets = normalize(dict(operation=OPERATION, tasks=tasks,
                             confirm_idle=confirm_idle, review_note=review_note))
    before, after, attempted = [], [], []
    stage = 'preflight'
    obj = schematic.SimulationTask

    def read(row):
        name = row['task_name']
        obj.Reset()
        obj.Name(name)
        if not obj.DoesExist():
            raise ValueError('Existing task required: ' + name)
        kind = str(obj.GetTypeForTask(name)).strip().lower()
        if kind != row['expected_type']:
            raise ValueError('Native task type differs: ' + name)
        raw = str(obj.GetProperty('enabled')).strip().lower()
        if raw not in ('true', 'false'):
            raise ValueError('Unknown native enabled state: ' + name)
        return {'task_name': name, 'type': kind, 'enabled': raw == 'true'}

    try:
        # Validate the entire target set before the first potentially mutating call.
        for row in targets:
            current = read(row)
            before.append(current)
            if current['enabled'] != row['expected_enabled']:
                raise ValueError('Native enabled state changed since review: ' + row['task_name'])
        stage = 'disable'
        for row in targets:
            current = read(row)
            if current['enabled'] != row['expected_enabled']:
                raise ValueError('Native enabled state changed before write: ' + row['task_name'])
            if current['enabled']:
                attempted.append(row['task_name'])
                obj.SetProperty('enabled', 'False')
        stage = 'readback'
        for row in targets:
            current = read(row)
            after.append(current)
            if current['enabled']:
                raise ValueError('Native task remains enabled: ' + row['task_name'])
    except Exception as exc:
        raise CircuitError('circuit_build_partial' if attempted else 'circuit_spec_invalid', str(exc),
            stage=stage, requested=targets, before=before, after=after, attempted=attempted,
            idle_asserted_by_caller=True, solver_verified=False) from exc
    return {'requested': targets, 'before': before, 'after': after, 'attempted': attempted,
            'review_note': review_note, 'idle_asserted_by_caller': True, 'idle_verified': False,
            'readback_verified': True, 'solver_verified': False, 'saved_reopen_verified': False,
            'result_retention_verified': False}
