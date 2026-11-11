"""Bounded native queries. Never add history, rebuild, save, or execute user code."""
import math

from tpc_service.errors import ServiceError

LIMIT = 10000


def validate_options(params):
    def require(condition, message):
        if not condition:
            raise ServiceError('invalid_session_argument', message)
    require(not set(params) - {'project_id', 'depends_on', 'native_readback',
                               'parameter_names', 'solid_names', 'sample_points', 'discrete_port_ids',
                               'read_only_review', 'confirm_idle', 'expected_digest'},
            'Unsupported inspect option')
    require(type(params.get('native_readback', False)) is bool, 'native_readback must be boolean')
    require(type(params.get('read_only_review', False)) is bool, 'read_only_review must be boolean')
    if params.get('read_only_review'):
        require(params.get('native_readback') is True and params.get('confirm_idle') is True,
                'Read-only review requires native_readback and caller-confirmed idle')
        value = params.get('expected_digest')
        require(isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value),
                'Read-only review requires explicit saved expected_digest')
    else:
        require(not set(params) & {'confirm_idle', 'expected_digest'}, 'Review fields require read_only_review=true')
    for key in ('parameter_names', 'solid_names'):
        if key in params:
            names = params[key]
            require(isinstance(names, list) and len(names) <= LIMIT and
                    all(isinstance(n, str) and 0 < len(n) <= 512 for n in names),
                    key + ' must be a bounded list of names')
    if 'discrete_port_ids' in params:
        from cst_automation.discrete_ports import validate_ids
        try:
            validate_ids(params['discrete_port_ids'])
        except ValueError as exc:
            raise ServiceError('invalid_session_argument', str(exc)) from exc
    points = params.get('sample_points', [])
    require(isinstance(points, list) and len(points) <= LIMIT, 'Bounded sample_points required')
    ids = set()
    for item in points:
        require(isinstance(item, dict) and set(item) == {'id', 'solid', 'point'}, 'Point requires id, solid, point')
        require(all(isinstance(item[k], str) and 0 < len(item[k]) <= 512 for k in ('id', 'solid')),
                'Sample ID and solid name required')
        require(item['id'] not in ids, 'Sample IDs must be unique')
        ids.add(item['id'])
        point = item['point']
        require(isinstance(point, list) and len(point) == 3 and
                all(type(x) in (int, float) and math.isfinite(x) for x in point), 'Finite xyz point required')
    require(params.get('native_readback', False) or not any(k in params for k in
            ('parameter_names', 'solid_names', 'sample_points', 'discrete_port_ids')), 'Query options require native_readback=true')


def inspect_native(app, params):
    if 'discrete_port_ids' in params:
        from cst_automation.discrete_ports import validate_ids
        validate_ids(params['discrete_port_ids'])
    result = dict(native_executed=True, parameters={}, solids={}, sample_points=[], errors=[],
                  coordinate_units='project geometry units', volume_units='project geometry units cubed')
    model = app.cst_file.model3d

    def query(label, callback):
        try:
            return callback()
        except Exception as exc:
            result['errors'].append(dict(query=label, error=repr(exc)))
            return None

    def enumerate_names(count, name):
        size = int(count())
        if not 0 <= size <= LIMIT:
            raise ValueError('Model enumeration exceeds inspection limit; supply explicit names')
        return [str(name(i)) for i in range(size)]

    names = params.get('parameter_names')
    if names is None:
        names = query('parameter_names', lambda: enumerate_names(model.GetNumberOfParameters, model.GetParameterName))
    for name in names or []:
        value = query('parameter:' + name, lambda: dict(value=app.get_parameter(name),
                        expression=str(model.RestoreParameterExpression(name))))
        if value is not None:
            result['parameters'][name] = value
    names = params.get('solid_names')
    if names is None:
        names = query('solid_names', lambda: enumerate_names(model.Solid.GetNumberOfShapes,
                                                             model.Solid.GetNameOfShapeFromIndex))
    def solid_data(name):
        if not model.Solid.DoesExist(name):
            raise KeyError(name)
        volume = float(model.Solid.GetVolume(name))
        if not math.isfinite(volume) or volume < 0:
            raise ValueError('Invalid native volume')
        return dict(material=str(model.Solid.GetMaterialNameForShape(name)), volume=volume)
    for name in names or []:
        value = query('solid:' + name, lambda: solid_data(name))
        if value is not None:
            result['solids'][name] = value
    for item in params.get('sample_points', []):
        def point_data():
            if not model.Solid.DoesExist(item['solid']):
                raise KeyError(item['solid'])
            return bool(model.Solid.IsPointInsideShape(*item['point'], item['solid']))
        inside = query('point:' + item['id'], point_data)
        if inside is not None:
            result['sample_points'].append(dict(item, inside=inside))
    if 'discrete_port_ids' in params:
        from cst_solver.simulation.discrete_ports import read_discrete_ports
        result['discrete_ports'] = query('discrete_ports', lambda: read_discrete_ports(app, params['discrete_port_ids']))
    return result
