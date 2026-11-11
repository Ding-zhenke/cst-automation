"""SDK-free command builder for linear ports on two ordered edge picks."""
import math

CAPABILITY = 'picked-face-port-controls-v1'
METHOD = 'create_discrete_face_port'


def _expression(value):
    if type(value) in (int, float) and math.isfinite(value):
        return str(value)
    if (isinstance(value, str) and value.strip()
            and not any(ord(c) < 32 or c == '"' or ord(c) == 127 for c in value)):
        try:
            numeric = float(value)
        except ValueError:
            return value
        if not math.isfinite(numeric):
            raise ValueError('Finite expression required')
        return value
    raise ValueError('Finite number or single-line CST expression required')


def face_port_code(r0, id_val, fold='', invert_direction=False, *, label='',
                   monitor=True, p1=(0, 0, 0), p2=(0, 0, 0)):
    if isinstance(id_val, str) and id_val.isascii() and id_val.isdecimal():
        id_val = int(id_val)
    if type(id_val) is not int or not 1 <= id_val <= 2147483647:
        raise ValueError('Positive port number required')
    if fold != '':
        raise ValueError('No documented DiscreteFacePort.Folder command; use label')
    if type(invert_direction) is not bool or type(monitor) is not bool:
        raise ValueError('Boolean direction and monitor required')
    if not isinstance(label, str) or any(ord(c) < 32 or ord(c) == 127 for c in label):
        raise ValueError('Single-line label required')
    impedance = _expression(r0)
    try:
        numeric_impedance = float(impedance)
    except ValueError:
        numeric_impedance = None
    if numeric_impedance is not None and (not math.isfinite(numeric_impedance) or numeric_impedance <= 0):
        raise ValueError('Positive impedance required')
    points = []
    for point in (p1, p2):
        if not isinstance(point, (list, tuple)) or len(point) != 3:
            raise ValueError('Three reference coordinates required per picked point')
        points.append(', '.join('"' + _expression(value) + '"' for value in point))
    label = label.replace('"', '""')
    return f'''With DiscreteFacePort
 .Reset
 .PortNumber "{id_val}"
 .Type "SParameter"
 .Label "{label}"
 .Impedance "{impedance}"
 .VoltageAmplitude "1.0"
 .CurrentAmplitude "1.0"
 .SetP1 "True", {points[0]}
 .SetP2 "True", {points[1]}
 .Monitor "{monitor}"
 .CenterEdge "True"
 .LocalCoordinates "False"
 .InvertDirection "{invert_direction}"
 .UseProjection "False"
 .ReverseProjection "False"
 .FaceType "Linear"
 .Create
End With'''
