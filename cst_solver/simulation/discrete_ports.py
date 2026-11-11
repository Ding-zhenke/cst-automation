"""Read documented getters on an already owned app, on its SDK thread."""
from cst_automation.discrete_ports import validate_ids
from cst_automation.port_replacement import number


def _tuple(value, size, label):
    if not isinstance(value, (tuple, list)) or len(value) != size or value[0] is not True:
        raise ValueError(f'Invalid or unsuccessful native {label}')
    return list(value)


def read_discrete_ports(app, port_ids):
    """Return an all-or-error snapshot; never connect, save, build or solve."""
    ids = validate_ids(port_ids)
    model = app.cst_file.model3d
    for pid in ids:
        if model.Port.GetType(pid) != 'Discrete':
            raise ValueError(f'Port {pid} is not a native Discrete port')
    native = model.DiscretePort
    result = {}
    for pid in ids:
        coordinates = _tuple(native.GetCoordinates(pid), 7, 'coordinates')
        xyz = [number(value) for value in coordinates[1:]]
        properties = _tuple(native.GetProperties(pid), 8, 'properties')
        if properties[1] not in ('SParameter', 'Voltage', 'Current') or type(properties[7]) is not bool:
            raise ValueError('Invalid native discrete-port type or monitor')
        for value in properties[2:7]:
            number(value)
        length = number(native.GetLength(pid))
        if length < 0:
            raise ValueError('Invalid native discrete-port length')
        result[str(pid)] = dict(
            start=xyz[:3], end=xyz[3:], length=length,
            coordinate_units='project geometry units',
            properties=dict(zip(('type', 'impedance_ohms', 'current', 'voltage',
                                 'voltage_port_impedance_ohms', 'radius', 'monitor'), properties[1:])),
            raw=dict(coordinates=coordinates, properties=properties, length=length))
    return result
