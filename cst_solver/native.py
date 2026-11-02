"""Explicit native adapters; importing this module does not load the CST SDK.

Command references: CST 2026 Online Help, VBA_DES CircuitProbe and Net objects.
Builders produce code only. They do not establish native readback acceptance.
"""

__all__ = ['vba_capabilities', 'execute_vba', 'circuit_probe_code', 'new_net_code']

_METHODS = {'model3d': ('_execute_vba_code', 'execute_vba_code'),
            'schematic': ('execute_vba_code',)}


def vba_capabilities(project):
    """Inspect callable attributes only; never try executing guessed methods."""
    return {target: next((name for name in names
                          if callable(getattr(getattr(project, target, None), name, None))), None)
            for target, names in _METHODS.items()}


def execute_vba(project, code, *, target, timeout=None):
    """Execute once on an explicit target, preserving the native return/exception."""
    if target not in _METHODS:
        raise ValueError('target must be model3d or schematic')
    method = vba_capabilities(project)[target]
    if method is None:
        raise NotImplementedError(f'{target}: supported VBA executor unavailable')
    execute = getattr(getattr(project, target), method)
    return execute(code, **({'timeout': timeout} if timeout is not None else {}))


def _quote(value):
    value = str(value)
    if any(c in value for c in '\r\n\x00'):
        raise ValueError('VBA strings cannot contain line breaks or NUL')
    return '"' + value.replace('"', '""') + '"'


def _probe_pin(pin):
    if len(pin) != 3 or pin[0] not in ('B', 'P'):
        raise ValueError('probe pin must be (B|P, component_name, pin_name)')
    return ', '.join(_quote(value) for value in pin)


def circuit_probe_code(name, pin, reference=None, *, direction_inwards=True):
    """Build a CircuitProbe macro; pin names are distinct from Net port indices."""
    if not isinstance(direction_inwards, bool):
        raise ValueError('direction_inwards must be bool')
    lines = ['Sub Main', 'With CircuitProbe', '    .Reset', f'    .Name {_quote(name)}',
             f'    .SetBlockPin {_probe_pin(pin)}, {direction_inwards}']
    if reference is not None:
        lines.append(f'    .SetRefBlockPin {_probe_pin(reference)}')
    return '\n'.join(lines + ['    .Create', 'End With', 'End Sub'])


def new_net_code(component_ports):
    """Create a generated net and check each pin after Apply; no manual net name."""
    ports = list(component_ports)
    if len(ports) < 2:
        raise ValueError('at least two component ports required')
    lines = ['Sub Main', f'Dim ComponentPorts({len(ports)-1}, 2) As Variant',
             'Dim GeneratedNetName As String']
    for i, port in enumerate(ports):
        if (len(port) != 3 or port[0] not in ('Block', 'Externalport', 'Probe') or
                isinstance(port[2], bool) or not isinstance(port[2], int) or port[2] < 0):
            raise ValueError('net port must be (Block|Externalport|Probe, name, nonnegative index)')
        for j, value in enumerate(port):
            lines.append(f'ComponentPorts({i}, {j}) = {_quote(value) if j < 2 else value}')
    lines += ['With Net', '    .Reset',
              '    GeneratedNetName = .AddComponentPorts("", ComponentPorts, False)',
              '    .Apply',
              '    If GeneratedNetName = "" Then Err.Raise  vbObjectError + 1, "Net", "Empty net name"']
    for kind, name, index in ports:
        lines += [f'    If .GetNetName(Array({_quote(kind)}, {_quote(name)}, {index})) <> GeneratedNetName Then _',
                  '        Err.Raise vbObjectError + 2, "Net", "Net readback mismatch"']
    return '\n'.join(lines + ['End With', 'End Sub'])
