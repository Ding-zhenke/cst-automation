"""Existing-task configuration only; no save, result readers or execution calls."""
from cst_automation.task_disable import normalize, OPERATION
from .adapter import CircuitError


def disable_tasks(schematic, tasks, *, confirm_idle, review_note):
    targets = normalize(dict(operation=OPERATION, tasks=tasks,
                             confirm_idle=confirm_idle, review_note=review_note))
    before, after, attempted = [], [], []
    observations = []
    ordered = sorted(targets, key=lambda row: -row['task_name'].count('\\'))
    execution_order = [row['task_name'] for row in ordered]
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

    def snapshot(phase, target):
        values = []
        observations.append({'phase': phase, 'target': target, 'targets': values})
        for item in targets:
            values.append(read(item))
        return values

    try:
        # Validate the entire target set before the first potentially mutating call.
        for row in targets:
            current = read(row)
            before.append(current)
            if current['enabled'] != row['expected_enabled']:
                raise ValueError('Native enabled state changed since review: ' + row['task_name'])
        expected = [dict(row) for row in before]
        # Descendants first: a parent's disable can affect child effective state.
        # Do not waive drift checks or infer which native enable bit a getter reads.
        for row in ordered:
            stage = 'before_write'
            observed = snapshot(stage, row['task_name'])
            if observed != expected:
                raise ValueError('Native target states changed before write: ' + row['task_name'])
            # Snapshot selected its last row. Explicitly reselect this write target.
            current = read(row)
            previous = next(item for item in expected if item['task_name'] == row['task_name'])
            if current != previous:
                raise ValueError('Native enabled state changed before write: ' + row['task_name'])
            if current['enabled']:
                stage = 'disable'
                attempted.append(row['task_name'])
                obj.SetProperty('enabled', 'False')
            previous['enabled'] = False
            stage = 'after_write'
            after = snapshot(stage, row['task_name'])
            if after != expected:
                raise ValueError('Native target states differ after disable: ' + row['task_name'])
        stage = 'readback'
        after = snapshot(stage, None)
        if after != expected:
            raise ValueError('Native target states changed at final readback')
    except Exception as exc:
        raise CircuitError('circuit_build_partial' if attempted else 'circuit_spec_invalid', str(exc),
            stage=stage, requested=targets, before=before, after=after, attempted=attempted,
            execution_order=execution_order, observations=observations,
            idle_asserted_by_caller=True, solver_verified=False) from exc
    return {'requested': targets, 'before': before, 'after': after, 'attempted': attempted,
            'execution_order': execution_order, 'observations': observations,
            'review_note': review_note, 'idle_asserted_by_caller': True, 'idle_verified': False,
            'readback_verified': True, 'solver_verified': False, 'saved_reopen_verified': False,
            'result_retention_verified': False}
