"""Common intrinsic diode and file-based SPICE configuration. No CST access."""
import math

from .circuit_configuration import require, configuration_name, quantity, file_snapshot
from .circuit_schema import SI_UNITS


# Native names are case-sensitive, including CST's spelling of the parameters.
DIODE_PARAMETERS = {
    'IS': ('Saturation current', 'Current', True),
    'N': ('Emission coefficient', None, True),
    'RS': ('Series resistance', 'Resistance', False),
    'CJO': ('Zero-bias depletion capacitance', 'Capacitance', False),
    'TT': ('Transit time', 'Time', False),
    'BV': ('Reverse breakdown voltage', 'Voltage', True),
    'IBV': ('Current at breakdown voltage', 'Current', True),
    'VJ': ('Built-in junction potential', 'Voltage', True),
    'M': ('Junction grading coefficient', None, False),
    'XTI': ('Saturation current temperature exponent', None, False),
    'AREA': ('Relative Device Area', None, True),
}


def nonlinear_model_settings(settings):
    require(isinstance(settings, dict), 'Nonlinear model settings must be a mapping')
    kind = settings.get('kind')
    if kind == 'berkeley_diode':
        require(not set(settings) - {'kind', 'parameters'}, 'Unknown diode settings')
        params = settings.get('parameters', {})
        require(isinstance(params, dict) and not set(params) - set(DIODE_PARAMETERS), 'Unknown diode parameters')
        props, units = {'Model Type': 2}, {}
        for key, value in params.items():
            native, dimension, strict = DIODE_PARAMETERS[key]
            if dimension:
                number = quantity(value, dimension, strict=strict)
                unit = SI_UNITS[dimension]
            else:
                require(type(value) in (int, float) and math.isfinite(value), 'Finite dimensionless numeric parameter required')
                require(value > 0 if strict else value >= 0, 'Diode parameter out of range')
                number, unit = value, '1'
            props[native], units[native] = number, unit
        return {'kind': kind, 'type': 'CircuitSemi\\Diode', 'properties': props, 'property_units': units, 'files': []}
    require(kind == 'spice', 'Model kind must be berkeley_diode/spice')
    require(not set(settings) - {'kind', 'file', 'model', 'dialect'}, 'Unknown SPICE settings')
    model = configuration_name(settings.get('model'))
    require(not any(c.isspace() for c in model), 'SPICE subcircuit name cannot contain whitespace')
    dialect = settings.get('dialect')
    require(dialect is None or dialect in ('AUTOMATIC', 'SPICE3', 'PSPICE', 'HSPICE'), 'Unsupported SPICE dialect')
    source = file_snapshot(settings.get('file'))
    return {'kind': kind, 'type': 'SPICEImport', 'file': source['path'], 'spice_model': model,
            'spice_filter': dialect, 'properties': {}, 'property_units': {}, 'files': [source]}
