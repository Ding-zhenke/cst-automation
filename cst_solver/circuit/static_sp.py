"""Bounded source disconnection primitive; no task creation or solve."""
from .adapter import CircuitError
import copy
import hashlib
import math
from pathlib import Path


def _scalar(expression, parameters):
    text = str(expression).strip()
    seen = set()
    while text in parameters:
        if text in seen:
            raise ValueError('Cyclic source resistance parameter')
        seen.add(text)
        text = str(parameters[text]).strip()
    value = float(text)
    if not math.isfinite(value):
        raise ValueError('Nonfinite source resistance')
    return value


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _endpoint(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 3 or
            not isinstance(value[0], str) or not isinstance(value[1], str) or not value[1] or
            type(value[2]) is not int or value[2] < 0):
        raise ValueError('Explicit native endpoint required')
    kind = {'b': 'block', 'block': 'block', 'p': 'externalport', 'externalport': 'externalport',
            'probe': 'probe'}.get(value[0].lower())
    if not kind:
        raise ValueError('Unsupported endpoint type')
    return (kind, value[1], value[2])


def _nets(obj):
    obj.Reset()
    count = obj.GetNumberOfNets()
    if type(count) is not int or not 0 <= count <= 10000:
        raise ValueError('Invalid net count')
    result = {}
    for i in range(count):
        name = str(obj.GetNetNameByIndex(i))
        if not name or name in result:
            raise ValueError('Duplicate or empty net')
        count_sub = obj.GetNumberOfSubnets(name)
        if type(count_sub) is not int or not 1 <= count_sub <= 10000:
            raise ValueError('Invalid subnet count')
        parts = [frozenset(_endpoint(v) for v in obj.GetComponentPorts(name, j)) for j in range(count_sub)]
        members = frozenset(_endpoint(v) for v in obj.GetComponentPorts(name, -1))
        if not members or set().union(*parts) != set(members) or sum(map(len, parts)) != len(members):
            raise ValueError('Inconsistent native subnet membership')
        result[name] = (members, parts)
    seen = set()
    for members, _ in result.values():
        if seen.intersection(members):
            raise ValueError('Endpoint appears in multiple native nets')
        seen.update(members)
    return result


def detach_source_endpoint(adapter, net_name, endpoint, expected_members):
    """Remove one exact source endpoint, fencing any uncertain mutation."""
    point = _endpoint(endpoint)
    if point[0] != 'block' or not isinstance(net_name, str) or not net_name:
        raise ValueError('Explicit source block and net required')
    if not isinstance(expected_members, list) or not expected_members:
        raise ValueError('Explicit complete original net membership required')
    members = [_endpoint(x) for x in expected_members]
    if len(set(members)) != len(members):
        raise ValueError('Duplicate expected endpoint')
    block = adapter.select('Block', point[1])
    if not block.DoesExist() or str(block.GetTypeName()).casefold() not in (
            'voltage dc source', 'voltage signal source', 'current dc source', 'current signal source'):
        raise ValueError('Target is not a supported source')
    obj = adapter.schematic.Net
    before = _nets(obj)
    if net_name not in before or before[net_name][0] != frozenset(members) or point not in before[net_name][0]:
        raise ValueError('Source endpoint or complete net membership changed')
    if len(before[net_name][0]) < 3 or sum(point in v[0] for v in before.values()) != 1:
        raise ValueError('Removal would leave an insufficient or ambiguous net')
    desired = {k: (v[0] - {point}, [p - {point} for p in v[1] if p - {point}]) if k == net_name else v
               for k, v in before.items()}
    try:
        obj.RemoveComponentPorts([list(endpoint)], net_name)
        obj.Apply()
        after = _nets(obj)
        def canonical(data):
            return {k: (v[0], frozenset(v[1])) for k, v in data.items()}
        if canonical(after) != canonical(desired):
            raise ValueError('Native net or subnet changed unexpectedly')
    except Exception as exc:
        raise CircuitError('circuit_build_partial', 'Source removal may be partially applied',
                           net_name=net_name, endpoint=list(endpoint)) from exc
    return {'net_name': net_name, 'removed_endpoint': list(endpoint),
            'before_members': expected_members, 'remaining_members': [list(x) for x in sorted(desired[net_name][0])],
            'readback_verified': True, 'solver_verified': False}


def replace_probe_with_measurement_port(adapter, net_name, probe_endpoint, port_endpoint, expected_members):
    """Replace one exact probe endpoint on a net with an already-created free port.

    Attach first so the original two-member net never becomes a singleton. The
    operation is intentionally not a full static-circuit or task transaction.
    """
    probe, port = _endpoint(probe_endpoint), _endpoint(port_endpoint)
    if probe[0] != 'probe' or port[0] != 'externalport' or not isinstance(net_name, str) or not net_name:
        raise ValueError('Explicit probe, external port and net required')
    if not isinstance(expected_members, list) or not expected_members:
        raise ValueError('Complete original net members required')
    members = [_endpoint(v) for v in expected_members]
    if len(set(members)) != len(members) or probe not in members or len(members) < 2:
        raise ValueError('Distinct original members containing the probe required')
    obj = adapter.schematic.Net
    before = _nets(obj)
    if (net_name not in before or before[net_name][0] != frozenset(members) or
            any(port in value[0] for value in before.values()) or
            sum(probe in value[0] for value in before.values()) != 1):
        raise ValueError('Original net differs or measurement port is already connected')
    if sum(probe in part for part in before[net_name][1]) != 1:
        raise ValueError('Probe subnet is ambiguous')
    try:
        result = obj.AddComponentPorts(net_name, [list(port_endpoint)], False)
        if str(result) != net_name:
            raise ValueError('Native net name changed')
        obj.Apply()
        attached = _nets(obj)
        if attached[net_name][0] != before[net_name][0] | {port} or any(
                attached.get(k) != v for k, v in before.items() if k != net_name):
            raise ValueError('Unexpected net change during attachment')
        prior = sorted(tuple(sorted(p)) for p in before[net_name][1])
        current = sorted(tuple(sorted(p - {port})) for p in attached[net_name][1] if p - {port})
        if current != prior:
            raise ValueError('Unexpected subnet change during attachment')
        obj.RemoveComponentPorts([list(probe_endpoint)], net_name)
        obj.Apply()
        after = _nets(obj)
        if (set(after) != set(before) or after[net_name][0] != (before[net_name][0] - {probe}) | {port}
                or any(after[k] != v for k, v in before.items() if k != net_name)):
            raise ValueError('Unexpected net change during probe removal')
        wanted = sorted(tuple(sorted(p - {probe})) for p in before[net_name][1] if p - {probe})
        current = sorted(tuple(sorted(p - {port})) for p in after[net_name][1] if p - {port})
        if current != wanted:
            raise ValueError('Unexpected subnet change during probe removal')
    except Exception as exc:
        raise CircuitError('circuit_build_partial', 'Measurement port replacement may be partially applied',
                           net_name=net_name, probe=list(probe_endpoint), port=list(port_endpoint)) from exc
    return {'net_name': net_name, 'removed_probe': list(probe_endpoint), 'measurement_port': list(port_endpoint),
            'readback_verified': True, 'solver_verified': False}


def validate_prepare_spec(spec):
    """Validate the complete request without touching a CST object."""
    from tpc_service.sessions.linear_sp import validate_setup
    if not isinstance(spec, dict) or set(spec) != {'snapshot_sha256', 'network_block', 'network_sha256',
                                                  'ports', 'task', 'control'}:
        raise ValueError('Exact static preparation fields required')
    for key in ('snapshot_sha256', 'network_sha256'):
        value = spec[key]
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Explicit lowercase SHA256 required')
    if not isinstance(spec['network_block'], str) or not spec['network_block'].strip():
        raise ValueError('Explicit network block required')
    rows = spec['ports']
    if not isinstance(rows, list) or len(rows) != 2:
        raise ValueError('Exactly two RF measurement ports required')
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'name', 'position', 'net_name', 'expected_members', 'probe_endpoint'}:
            raise ValueError('Exact RF port and probe mapping required')
        if _endpoint(row['probe_endpoint'])[0] != 'probe':
            raise ValueError('Each RF replacement requires a probe endpoint')
    validate_setup({'project_id': 'p', 'network_job_id': 'n', 'task': spec['task'],
                    'ports': [{k: row[k] for k in ('name', 'position', 'net_name', 'expected_members')} for row in rows]})
    control = spec['control']
    keys = {'network_pin', 'probe', 'source', 'bias', 'ground', 'resistance_ohms'}
    if (not isinstance(control, dict) or set(control) != keys or type(control['network_pin']) is not int
            or control['network_pin'] < 0 or any(not isinstance(control[k], str) or not control[k].strip()
            for k in ('probe', 'source', 'bias', 'ground')) or type(control['resistance_ohms']) not in (int, float)
            or not math.isfinite(control['resistance_ohms']) or control['resistance_ohms'] <= 0):
        raise ValueError('Explicit control path and resistance required')


def prepare_static_sp(adapter, spec, *, before_write=None):
    """Prepare one static-only circuit; the owning session saves and fences errors."""
    from cst_automation.workflow import digest
    from .linear_sp import configure_linear_sp_task
    validate_prepare_spec(spec)
    rows, control = spec['ports'], spec['control']
    before = adapter.inspect()
    if digest(before) != spec['snapshot_sha256'] or any(u != {'field': 'parameter_dimensions', 'status': 'unknown'}
                                                         for u in before.get('unknown', [])):
        raise ValueError('Native circuit snapshot changed or is incomplete')
    if before.get('external_ports') or any(t.get('name') == spec['task']['task_name'] for t in before.get('tasks', [])):
        raise ValueError('Existing external ports or SP task require a different supported path')
    blocks = {b['name']: b for b in before['blocks']}
    if len(blocks) != len(before['blocks']):
        raise ValueError('Duplicate block names')
    target = adapter.select('Block', spec['network_block'])
    if not target.DoesExist() or str(target.GetTypeName()) != 'TOUCHSTONE block':
        raise ValueError('Existing embedded Touchstone network required')
    network_path = Path(str(target.GetFile()))
    project_path = Path(adapter.app.cst_file.filename()).resolve()
    network_root = project_path.with_suffix('') / 'Model' / 'DS' / 'Block'
    if not network_path.is_absolute() or not network_path.resolve().is_relative_to(network_root.resolve()) or _sha(network_path) != spec['network_sha256']:
        raise ValueError('Embedded network location or digest differs')
    dependencies = adapter.dependencies()
    if (dependencies.get('complete') is not True or dependencies.get('unknown') or
            any(not row.get('exists') or not row.get('sha256') for row in dependencies.get('files', []))):
        raise ValueError('Native circuit dependency inventory incomplete')
    nets = _nets(adapter.schematic.Net)
    def connected(a, b):
        return sum(_endpoint(a) in v[0] and _endpoint(b) in v[0] for v in nets.values()) == 1
    network = spec['network_block']; probe = control['probe']; source = control['source']; bias = control['bias']; ground = control['ground']
    chain = [([ 'Block', network, control['network_pin']], ['Probe', probe, 1]),
             (['Probe', probe, 0], ['Block', source, 0]),
             (['Block', source, 1], ['Block', bias, 0]),
             (['Block', bias, 1], ['Block', ground, 0])]
    if not all(connected(a, b) for a, b in chain):
        raise ValueError('Native control termination chain differs')
    for a, b in chain[:3]:
        if next(v[0] for v in nets.values() if _endpoint(a) in v[0] and _endpoint(b) in v[0]) != frozenset((_endpoint(a), _endpoint(b))):
            raise ValueError('Control path has an additional parallel branch')
    if (blocks.get(source, {}).get('type', '').casefold() != 'voltage signal source' or
            blocks.get(bias, {}).get('type', '').casefold() != 'voltage dc source' or
            blocks.get(ground, {}).get('type', '').casefold() != 'ground'):
        raise ValueError('Control path block types differ')
    for name, required in ((source, {0, 1}), (bias, {0, 1}), (ground, {0})):
        pins = blocks[name].get('pins')
        if (not isinstance(pins, list) or len(pins) != len(required) or
                {p.get('port_index') for p in pins} != required):
            raise ValueError('Control block native pin inventory differs')
    parameters = before.get('parameters', {})
    for name, expected in ((source, control['resistance_ohms']), (bias, 0)):
        prop = blocks[name].get('properties', {})
        meta = blocks[name].get('property_metadata', {}).get('Ri', {})
        if meta.get('unit') != 'Ohm' or not math.isclose(_scalar(prop['Ri'], parameters), expected, rel_tol=1e-12, abs_tol=0):
            raise ValueError('Control source resistance differs')
    sources = []
    for block in before['blocks']:
        kind = str(block['type']).casefold()
        if 'source' not in kind:
            continue
        if kind in ('voltage dc source', 'current dc source'):
            fields = ('DC',)
        elif kind in ('voltage signal source', 'current signal source'):
            fields = ('ACAmplitude', 'HBAmplitude')
        else:
            raise ValueError('Unsupported independent source type')
        if any(field not in block.get('properties', {}) for field in fields):
            raise ValueError('Source property readback incomplete')
        sources.append((block['name'], fields))
    if not sources:
        raise ValueError('Source inventory missing')
    for row in rows:
        point = _endpoint(row['probe_endpoint'])
        expected = frozenset(_endpoint(v) for v in row['expected_members'])
        if (row['net_name'] not in nets or nets[row['net_name']][0] != expected or point not in expected or
                point[2] not in (0, 1) or point[1] == probe or len(expected) != 2 or
                not any(v[0] == 'block' and v[1] == network and v[2] != control['network_pin'] for v in expected)):
            raise ValueError('RF probe/net mapping differs')
        other = ('probe', point[1], 1 - point[2])
        matches = [v[0] for v in nets.values() if other in v[0]]
        if len(matches) != 1 or len(matches[0]) != 2:
            raise ValueError('RF probe source-side branch is not isolated')
        source_endpoints = [v for v in matches[0] if v != other and v[0] == 'block']
        if (len(source_endpoints) != 1 or source_endpoints[0][1] in (source, bias) or
                blocks.get(source_endpoints[0][1], {}).get('type', '').casefold() not in
                ('voltage signal source', 'current signal source')):
            raise ValueError('RF probe does not exclusively connect to an RF signal source')
    # All checks above occur before any native write. Partial failures never roll back automatically.
    report = {'before': copy.deepcopy(before), 'dependencies_before': dependencies,
              'network_sha256': spec['network_sha256'], 'changes': [],
              'control_path_verified': False, 'solver_verified': False}
    if before_write is not None:
        before_write(copy.deepcopy(report))
    try:
        for name, fields in sources:
            obj = adapter.select('Block', name)
            for field in fields:
                obj.SetDoubleProperty(field, '0')
                if float(str(obj.GetProperty(field))) != 0:
                    raise ValueError('Source zero readback differs')
                report['changes'].append({'source': name, 'property': field, 'value': '0'})
        for row in rows:
            obj = adapter.schematic.ExternalPort
            obj.Reset(); obj.Name(row['name']); obj.Position(*row['position']); obj.Create()
            obj.Reset(); obj.Name(row['name'])
            if int(obj.GetNumberOfPorts()) != 1:
                raise ValueError('New measurement port must have one endpoint')
            report['changes'].append(replace_probe_with_measurement_port(adapter, row['net_name'], row['probe_endpoint'],
                                      ['ExternalPort', row['name'], 0], row['expected_members']))
        task = spec['task']
        report['task'] = configure_linear_sp_task(adapter.schematic, task['task_name'], frequency_unit=task['frequency_unit'],
            fmin=task['fmin'], fmax=task['fmax'], samples=task['samples'], port_impedances=task['port_impedances'])
        after = adapter.inspect()
        if any(u != {'field': 'parameter_dimensions', 'status': 'unknown'} for u in after.get('unknown', [])):
            raise ValueError('Post-configuration readback incomplete')
        if (Path(str(adapter.select('Block', network).GetFile())).resolve() != network_path.resolve() or
                _sha(network_path) != spec['network_sha256'] or adapter.dependencies() != dependencies):
            raise ValueError('Embedded network changed')
        for name in (source, bias):
            actual = adapter.property_readback(name)
            if actual['properties']['Ri'] != blocks[name]['properties']['Ri'] or actual['property_metadata']['Ri'] != blocks[name]['property_metadata']['Ri']:
                raise ValueError('Control source impedance changed')
        after_blocks = {b['name']: b for b in after['blocks']}
        source_fields = dict(sources)
        for name, block in blocks.items():
            if name not in source_fields and after_blocks.get(name) != block:
                raise ValueError('Non-source block or diode changed')
            if name in source_fields:
                previous, current_source = copy.deepcopy(block), copy.deepcopy(after_blocks.get(name))
                if not isinstance(current_source, dict):
                    raise ValueError('Source block missing')
                for field in source_fields[name]:
                    if float(str(current_source['properties'][field])) != 0:
                        raise ValueError('Source zero setting changed')
                    current_source['properties'][field] = previous['properties'][field]
                if current_source != previous:
                    raise ValueError('Source connection, impedance, metadata or other property changed')
        if set(after_blocks) != set(blocks) or any(after.get(k) != before.get(k) for k in ('parameters', 'units', 'probes')):
            raise ValueError('Unrelated circuit contents changed')
        if ({p['name'] for p in after['external_ports']} != {row['name'] for row in rows} or
                [t for t in after['tasks'] if t['name'] != task['task_name']] != before['tasks'] or
                len([t for t in after['tasks'] if t['name'] == task['task_name']]) != 1):
            raise ValueError('External port or task inventory differs')
        report['after'] = after
        report['dependencies_after'] = dependencies
        report['isolated_source_branches_solver_validity'] = 'unverified'
        report['control_path_verified'] = all(connected(a, b) for a, b in chain)
        # Re-read nets after mutation, not the cached preflight dictionary.
        current = _nets(adapter.schematic.Net)
        if not all(sum(_endpoint(a) in v[0] and _endpoint(b) in v[0] for v in current.values()) == 1 for a, b in chain):
            raise ValueError('Control path changed')
        report['control_path_verified'] = True
        return report
    except Exception as exc:
        raise CircuitError('circuit_build_partial', 'Static SP preparation partially applied',
                           stage='prepare_static_sp', original_error=str(exc),
                           original_details=getattr(exc, 'details', {}), partial=report) from exc
