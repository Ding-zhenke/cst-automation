"""Pure input contract for exact-ID, numeric, axis-aligned port replacement."""
import copy
import math

CAPABILITY = 'port-replacement-readback-v1'
METHOD = 'replace_port_with_waveguide'


def port_id(value):
    if type(value) is not int or not 1 <= value <= 2147483647:
        raise ValueError('Port ID must be an explicit positive integer')
    return value


def number(value):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError('Finite numeric coordinates in project units required')
    return value


def normalize(id_val, settings, *, expected_type, preserve_ports):
    port_id(id_val)
    if expected_type not in ('Discrete', 'Waveguide') or not isinstance(preserve_ports, dict):
        raise ValueError('Explicit original type and preserve_ports mapping required')
    for key, kind in preserve_ports.items():
        if not isinstance(key, str) or not key.isascii() or not key.isdecimal() or str(int(key)) != key:
            raise ValueError('Preserved IDs must be canonical decimal strings')
        if port_id(int(key)) == id_val or kind not in ('Discrete', 'Waveguide'):
            raise ValueError('Preserved port must be a different explicit ID/type')
    required = {'xrange', 'yrange', 'zrange', 'orientation', 'number_of_modes', 'port_on_bound'}
    if not isinstance(settings, dict) or not required <= set(settings) or set(settings) - required - {'shield', 'reference_plane_distance'}:
        raise ValueError('Explicit rectangular waveguide settings required')
    data = copy.deepcopy(settings)
    if data['orientation'] not in ('xmin','xmax','ymin','ymax','zmin','zmax'):
        raise ValueError('Explicit valid orientation required')
    for axis in 'xyz':
        bounds = data[axis+'range']
        if not isinstance(bounds, (list,tuple)) or len(bounds) != 2:
            raise ValueError('Each axis requires two numeric bounds')
        low, high = map(number, bounds)
        if (axis == data['orientation'][0] and low != high) or (axis != data['orientation'][0] and low >= high):
            raise ValueError('Nondegenerate face must match the port normal')
    if type(data['number_of_modes']) is not int or not 1 <= data['number_of_modes'] <= 100:
        raise ValueError('number_of_modes must be an integer from 1 to 100')
    if type(data['port_on_bound']) is not bool or data.get('shield','') not in ('','electric','magnetic'):
        raise ValueError('Explicit boolean boundary flag and supported shield required')
    number(data.get('reference_plane_distance',0))
    return data
