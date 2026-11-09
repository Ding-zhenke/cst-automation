"""CST-independent engineering contract validation. No SDK or executable rules."""
import copy
import hashlib
import json
import math


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Expected a finite real number')
    return value


def text(value):
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise ValueError('Expected nonempty text without control characters')
    return value


def within(value, rule):
    number(value)
    if 'value' in rule and value != rule['value']:
        raise ValueError('Fixed parameter cannot be changed')
    if 'min' in rule and value < rule['min'] or 'max' in rule and value > rule['max']:
        raise ValueError('Value outside approved limits')


def parameter_changes(spec, values):
    if not isinstance(values, dict) or not values:
        raise ValueError('Nonempty parameter changes required')
    for name, value in values.items():
        if name not in spec['parameters']:
            raise ValueError('Undeclared parameter: ' + str(name))
        within(value, spec['parameters'][name])


def normalize(spec):
    if not isinstance(spec, dict):
        raise ValueError('Workflow specification must be an object')
    data = copy.deepcopy(spec)
    required = {'schema_version', 'parameters', 'initial_values', 'em_checks', 'hb_checks',
                'hb_task', 'hb_request', 'evidence_rules'}
    if set(data) != required or type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise ValueError('Workflow schema v1 requires explicit fields only')
    if not isinstance(data['parameters'], dict) or not data['parameters']:
        raise ValueError('Explicit parameter rules required')
    from cst_solver.expressions import validate_parameter_name
    for name, rule in data['parameters'].items():
        if validate_parameter_name(name) != name:
            raise ValueError('Parameter names must be canonical')
        if not isinstance(rule, dict) or rule.get('affects') not in ('em', 'hb'):
            raise ValueError('Each parameter requires affects=em or hb')
        if set(rule) not in ({'value', 'affects'}, {'min', 'max', 'affects'}):
            raise ValueError('Use a fixed value or bounded independent numeric parameter')
        for key in set(rule) - {'affects'}:
            number(rule[key])
        if 'min' in rule and rule['min'] > rule['max']:
            raise ValueError('Reversed parameter limits')
    if not isinstance(data['initial_values'], dict) or set(data['initial_values']) != set(data['parameters']):
        raise ValueError('initial_values must cover every declared parameter')
    parameter_changes(data, data['initial_values'])
    for stage in ('em_checks', 'hb_checks'):
        checks = data[stage]
        if not isinstance(checks, list) or not checks:
            raise ValueError('Nonempty native checks required for ' + stage)
        for check in checks:
            if not isinstance(check, dict):
                raise ValueError('Native check must be an object')
            source = check.get('source')
            keys = {'source', 'name', 'expected'}
            if source in ('block_property', 'task_property'):
                keys.add('property')
                text(check.get('property'))
            elif source != 'parameter':
                raise ValueError('Unsupported native check source')
            if set(check) not in (keys, keys | {'atol'}):
                raise ValueError('Invalid native check fields')
            text(check['name'])
            expected = check['expected']
            if type(expected) in (int, float):
                number(expected)
                if number(check.get('atol', 0)) < 0:
                    raise ValueError('Negative tolerance')
            elif not isinstance(expected, str) or 'atol' in check:
                raise ValueError('Expected native value must be text or number, not a passed flag')
    text(data['hb_task'])
    request = data['hb_request']
    if not isinstance(request, dict) or request.get('mode') != 'network':
        raise ValueError('HB requires explicit network mode')
    if set(request) & {'operation', 'task_name', 'expected_results', 'reuse'}:
        raise ValueError('Reserved HB request fields')
    rules = data['evidence_rules']
    if not isinstance(rules, dict) or not rules:
        raise ValueError('Explicit numerical evidence rules required')
    for key, rule in rules.items():
        text(key)
        if not isinstance(rule, dict) or not rule or set(rule) - {'min', 'max'}:
            raise ValueError('Evidence rules require numeric min/max')
        for value in rule.values():
            number(value)
        if 'min' in rule and 'max' in rule and rule['min'] > rule['max']:
            raise ValueError('Reversed evidence limits')
    digest(data)  # Reject non-JSON values and NaN anywhere in the specification.
    return data
