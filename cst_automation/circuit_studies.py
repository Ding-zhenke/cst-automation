"""SDK-free specification for fixed-topology circuit parameter studies."""
import copy
import math
import re


def segment(value):
    if not isinstance(value, str) or not re.fullmatch(r'[\w-]+', value, re.UNICODE):
        raise ValueError('A nonempty name using letters, digits, underscores or hyphens is required')
    return value


def _keys(data, required, optional=()):
    if not isinstance(data, dict) or not set(required) <= data.keys() or data.keys() - set(required) - set(optional):
        raise ValueError('Missing or unsupported study fields; required: ' + ', '.join(required))


def _text(value):
    if not isinstance(value, str) or not value.strip() or any(c in value for c in '\r\n\x00'):
        raise ValueError('Nonempty text without control characters required')
    return value


def _results(results, task=None):
    if not isinstance(results, list) or not results:
        raise ValueError('Explicit nonempty result list required')
    names, paths = set(), set()
    for item in results:
        _keys(item, ('name', 'tree_path', 'run_id') if task else ('tree_path', 'run_id'))
        path = _text(item['tree_path'])
        if any(part in ('', '.', '..') for part in path.split('\\')):
            raise ValueError('Invalid result tree path')
        if path in paths:
            raise ValueError('Duplicate source result path')
        paths.add(path)
        if type(item['run_id']) is not int or item['run_id'] < 0:
            raise ValueError('Result run_id must be an explicit nonnegative integer')
        if task:
            name = segment(item['name'])
            if name in names:
                raise ValueError('Duplicate result name')
            names.add(name)
            if not path.startswith((task + '\\', 'Tasks\\' + task + '\\')):
                raise ValueError('Result must belong to the selected task')


def normalize_parameter_study(spec):
    """Validate the entire JSON-shaped plan before SDK access; no Cartesian expansion.

    Parameter values without a block binding use the declared native parameter
    units. With block/property, values are passed to the existing unit-aware
    property API. This function neither queries nor guesses native units.
    """
    _keys(spec, ('schema_version', 'name', 'parameters', 'points', 'task'), ('em',))
    if type(spec['schema_version']) is not int or spec['schema_version'] != 1:
        raise ValueError('Study schema_version must be 1')
    segment(spec['name'])
    parameters = spec['parameters']
    if not isinstance(parameters, dict) or not parameters:
        raise ValueError('At least one study parameter required')
    em_parameters = False
    targets = set()
    for name, item in parameters.items():
        segment(name)
        _keys(item, ('scope', 'unit'), ('block', 'property'))
        if item['scope'] not in ('em', 'circuit'):
            raise ValueError('Parameter scope must be em or circuit')
        _text(item['unit'])
        if ('block' in item) != ('property' in item):
            raise ValueError('Block and property must be supplied together')
        if 'block' in item:
            if item['scope'] != 'circuit':
                raise ValueError('Block properties are circuit parameters')
            _text(item['block']); _text(item['property'])
        target = (item['scope'], item.get('block'), item.get('property', name))
        if target in targets:
            raise ValueError('Multiple parameters bind the same native target')
        targets.add(target)
        em_parameters |= item['scope'] == 'em'
    points = spec['points']
    if not isinstance(points, list) or not points:
        raise ValueError('Explicit nonempty point list required')
    for point in points:
        _keys(point, ('values',))
        values = point['values']
        if not isinstance(values, dict) or values.keys() != parameters.keys():
            raise ValueError('Each point must specify exactly all study parameters')
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in values.values()):
            raise ValueError('Study values must be finite real numbers, not expressions or booleans')
    task = spec['task']
    _keys(task, ('name', 'mode', 'results'))
    name = _text(task['name'])
    if task['mode'] != 'network':
        raise ValueError('First study version supports network tasks; use existing transient_cosim API for bidirectional coupling')
    _results(task['results'], name)
    if em_parameters and 'em' not in spec:
        raise ValueError('EM parameters require an explicit EM dependency')
    if 'em' in spec:
        _keys(spec['em'], ('results',))
        _results(spec['em']['results'])
    return copy.deepcopy(spec)
