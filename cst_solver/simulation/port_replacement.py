"""Exact-ID replacement using documented Port methods on the owning app only."""
from types import SimpleNamespace
from cst_automation.port_replacement import normalize, port_id


class PortReplacementError(RuntimeError):
    def __init__(self, message, receipt):
        super().__init__(message)
        self.receipt = receipt


def port_inventory(app):
    port = app.cst_file.model3d.Port
    count = port.StartPortNumberIteration()
    if type(count) is not int or not 0 <= count <= 10000:
        raise ValueError('Native port inventory is invalid or exceeds the bound')
    result = {}
    for _ in range(count):
        pid = port_id(port.GetNextPortNumber())
        kind, modes = str(port.GetType(pid)), port.GetNumberOfModes(pid)
        if (kind not in ('Discrete','Waveguide') or type(modes) is not int
                or modes < (0 if kind == 'Discrete' else 1) or str(pid) in result):
            raise ValueError('Invalid/duplicate native port identity')
        result[str(pid)] = {'type': kind, 'number_of_modes': modes}
    return result


def preflight_batch(app, replacements):
    """Check all original identities before the first replacement in a batch."""
    report = {'stage': 'batch_preflight_readback', 'mutation_attempted': False}
    try:
        before = report['before'] = port_inventory(app)
        for values in replacements:
            pid = str(values['id_val'])
            if before.get(pid, {}).get('type') != values['expected_type']:
                raise ValueError(f'Target port {pid} differs from expected original type')
            if any(before.get(key, {}).get('type') != kind
                   for key, kind in values['preserve_ports'].items()):
                raise ValueError('Preserved port is missing or has a different type')
    except Exception as exc:
        raise PortReplacementError(str(exc), report) from exc


def replace_port_with_waveguide(app, id_val, settings, *, expected_type, preserve_ports):
    from .ports import PortMixin
    settings = normalize(id_val, settings, expected_type=expected_type, preserve_ports=preserve_ports)
    commands = []
    sink = SimpleNamespace(cst_file=SimpleNamespace(model3d=SimpleNamespace(
        add_to_history=lambda name, code: commands.append(code))))
    PortMixin.create_waveguide_port_free(sink, id_val, **settings)
    code = f'Port.Delete {id_val}\n' + commands[0]
    report = {'port_id': id_val, 'requested': settings, 'expected_type': expected_type,
              'preserve_ports': dict(preserve_ports), 'mutation_attempted': False,
              'identity_readback_verified': False, 'geometry_readback_verified': False,
              'mode_impedance_verified': False, 'preserved_ports_usable_verified': False,
              'native_commands': code, 'stage': 'preflight_readback'}
    try:
        before = report['before'] = port_inventory(app)
        if before.get(str(id_val), {}).get('type') != expected_type:
            raise ValueError('Target port is missing or differs from the expected original type')
        if any(before.get(pid, {}).get('type') != kind for pid, kind in preserve_ports.items()):
            raise ValueError('Preserved port is missing or has a different type')
        expected = {pid: dict(info) for pid, info in before.items()}
        expected[str(id_val)] = {'type':'Waveguide', 'number_of_modes':settings['number_of_modes']}
        report['stage'] = 'replace_history'
        report['mutation_attempted'] = True
        facade = getattr(app, '_circuit_facade', None)
        if facade is not None:
            facade._spec = None
        app.cst_file.model3d.add_to_history(f'Replace port {id_val} with waveguide', code)
        report['stage'] = 'post_readback'
        after = report['after'] = port_inventory(app)
        if after != expected:
            raise ValueError('Native port inventory differs after replacement')
        report.update(identity_readback_verified=True, stage='returned')
        return report
    except Exception as exc:
        raise PortReplacementError(str(exc), report) from exc


def verify_after_rebuild(app, receipts):
    replacements = [r for r in receipts if r['method'] == 'replace_port_with_waveguide']
    if not replacements:
        return
    report = {'stage':'post_rebuild_readback', 'mutation_attempted':True,
              'replacements':replacements}
    try:
        actual = port_inventory(app)
        report['actual'] = actual
        if actual != replacements[-1]['receipt']['after']:
            raise ValueError('Port identity changed during rebuild')
        for item in replacements:
            item['receipt']['post_rebuild_identity_verified'] = True
    except Exception as exc:
        raise PortReplacementError(str(exc), report) from exc
