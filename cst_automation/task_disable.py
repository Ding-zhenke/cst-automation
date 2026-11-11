"""Pure request contract for disabling existing DS tasks; never loads CST."""

CAPABILITY = 'disable-native-tasks-v2'
OPERATION = 'disable_tasks'


def normalize(settings):
    def require(ok, message):
        if not ok:
            raise ValueError(message)
    require(isinstance(settings, dict) and set(settings) == {
        'operation', 'tasks', 'confirm_idle', 'review_note'}, 'Exact disable_tasks fields required')
    require(settings['operation'] == OPERATION, 'Expected disable_tasks operation')
    require(settings['confirm_idle'] is True, 'Owning caller must confirm EM/DS/postprocessing idle')
    note = settings['review_note']
    require(isinstance(note, str) and 0 < len(note.strip()) <= 1000, 'Bounded nonempty review_note required')
    tasks = settings['tasks']
    require(isinstance(tasks, list) and 1 <= len(tasks) <= 32, 'Expected 1..32 explicit tasks')
    names, result = set(), []
    for row in tasks:
        require(isinstance(row, dict) and set(row) == {'task_name', 'expected_type', 'expected_enabled'},
                'Each target requires task_name, expected_type and expected_enabled')
        name = row['task_name']
        require(isinstance(name, str) and 0 < len(name) <= 1024 and name == name.strip()
                and not any(ord(c) < 32 for c in name) and '/' not in name
                and all(part and part.strip() == part and part not in ('.', '..') for part in name.split('\\'))
                and not name.startswith('Tasks\\'), 'Explicit full task name without Results tree prefix required')
        require(name not in names, 'Duplicate task target')
        require(row['expected_type'] in ('parameter sweep', 'spectral lines'), 'Expected native sweep or HB type')
        require(type(row['expected_enabled']) is bool, 'expected_enabled must be boolean')
        names.add(name)
        result.append(dict(row))
    return result


def is_request(operation, params):
    return operation == 'circuit' and params.get('settings', {}).get('operation') == OPERATION
