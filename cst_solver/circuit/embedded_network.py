"""Owned temporary LF fit and in-place embedded payload update, never a solve."""
from pathlib import Path
import copy
import math

import numpy as np

from cst_automation import embedded_network as data


def paths(project_path, output_path, job_id):
    # Job IDs are validated by the session store before reaching this boundary.
    import hashlib
    name = 'EMLF_' + hashlib.sha256(job_id.encode()).hexdigest()[:24]
    directory = Path(project_path).with_suffix('')/'Export'/'ABCD'
    return name, {key: str(directory/(name + ('.log' if key == 'log' else '_'+key+'.csv')))
                  for key in ('A', 'B', 'C', 'D', 'log')}, Path(output_path).with_stem(Path(output_path).stem+'_lf')


def snapshot(app, target):
    result = copy.deepcopy(app.circuit.adapter.inspect())
    unknown = [u for u in result.get('unknown', []) if u.get('field') != 'parameter_dimensions']
    if unknown or any(result.get(key) is None for key in ('blocks', 'nets', 'external_ports', 'probes', 'tasks', 'units', 'parameters')):
        raise ValueError('Circuit topology readback incomplete')
    blocks = [b for b in result['blocks'] if b['name'] == target]
    if len(blocks) != 1: raise ValueError('Existing target must be unique')
    # Only this file reference is expected to change. Preserve every other field.
    blocks[0]['files'] = []
    return result


def observe(app, p, project_path):
    adapter = app.circuit.adapter
    block = adapter.select('Block', p['block_name'])
    n = len(p['physical_port_ids'])
    if (block.DoesExist() is not True or str(block.GetTypeName()) != 'TOUCHSTONE block'
            or block.GetNumberOfFiles() != 1 or block.GetNumberOfPorts() != n
            or [str(block.GetPortName(i)) for i in range(n)] != [str(i+1) for i in range(n)]):
        raise ValueError('Expected existing single-file embedded block with sequential ports')
    path = Path(str(block.GetFile()))
    root = Path(project_path).with_suffix('')/'Model'/'DS'/'Block'
    if not path.is_absolute() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Effective embedded payload must be inside the owning Model/DS/Block')
    pins = adapter.pins(p['block_name'])
    if (len(pins) != n or {v.get('port_index') for v in pins} != set(range(n))
            or any(v.get('pin_name') != str(v['port_index']+1) for v in pins)):
        raise ValueError('Embedded native pin mapping incomplete')
    return {'path': str(path.resolve()), 'sha256': data.digest(path), 'pins': pins,
            'type': 'TOUCHSTONE block', 'physical_port_ids': list(p['physical_port_ids'])}


def prepare(app, p, project_path, job_id, save):
    f, s, indices = data.load_matrix(p)
    name, exports, lf_path = paths(project_path, p['output_path'], job_id)
    before = observe(app, p, project_path)
    if before['sha256'] != p['expected_payload_sha256']:
        raise ValueError('Original embedded payload changed')
    original = snapshot(app, p['block_name'])
    adapter = app.circuit.adapter
    if adapter.select('Block', name).DoesExist(): raise ValueError('Temporary block already exists')
    if any(Path(exports['A']).parent.glob(name+'*')) or lf_path.exists() or Path(p['output_path']).exists():
        raise ValueError('Owned fitting output already exists; refusing overwrite')
    unit = str(adapter.schematic.Units.GetUnit('Frequency'))
    scale = {'Hz': 1, 'kHz': 1e3, 'MHz': 1e6, 'GHz': 1e9}.get(unit)
    if scale is None: raise ValueError('Unknown schematic frequency unit')
    setters = {'fmax': ('SetConvolutionFmax', 'GetConvolutionFmax'),
               'accuracy_abs': ('SetMOR_AccuracyAbs', 'GetMOR_AccuracyAbs'),
               'maximum_poles': ('SetMOR_MaximumPoles', 'GetMOR_MaximumPoles'),
               'manual': ('SetMOR_ManualPoleChoice', 'GetMOR_ManualPoleChoice'),
               'enhance_dc': ('SetMOR_EnhanceAccuracyAtDC', 'GetMOR_EnhanceAccuracyAtDC'),
               'passivate': ('SetMOR_PassivateToInfinity', 'GetMOR_PassivateToInfinity'),
               'method': ('SetVectorFittingMethod', 'GetVectorFittingMethod'),
               'norm': ('SetMOR_ErrorNorm', 'GetMOR_ErrorNorm'),
               'natural': ('SetUseNaturalImpedances', 'GetUseNaturalImpedances'),
               'reference': ('SetMOR_RenormalizationImpedance', 'GetMOR_RenormalizationImpedance')}
    # Availability is resolved before creating a native object.
    block = adapter.schematic.Block
    for setter, getter in setters.values(): getattr(block, setter); getattr(block, getter)
    data.write_touchstone(lf_path, f[indices], s[indices], p['reference_ohm'])
    block.Reset(); block.Type('TouchstoneProjectInternal'); block.Name(name)
    # Explicit schematic coordinates, unrelated to physical model dimensions.
    block.SetFile(str(lf_path)); block.Position(15000, 15000); block.Create()
    created = snapshot(app, p['block_name'])
    created['blocks'] = [b for b in created['blocks'] if b['name'] != name]
    if created != original:
        raise ValueError('Temporary block creation changed the existing circuit')
    block = adapter.select('Block', name)
    if block.CanUseMOR() is not True: raise ValueError('Temporary LF block cannot use MOR')
    settings = dict(p['settings'], fmax=float(f[indices][-1]/scale), manual=False, method='BUILT-IN',
                    norm='Max', natural=False, reference=p['reference_ohm'])
    for key, value in settings.items():
        getattr(block, setters[key][0])(value if type(value) is bool else str(value))
    actual = {k: getattr(block, getter)() for k, (_, getter) in setters.items()}
    for key, value in settings.items():
        got = actual[key]
        if type(value) is bool: valid = type(got) is bool and got == value
        elif isinstance(value, str): valid = str(got).casefold() == value.casefold()
        else: valid = math.isclose(float(got), value, rel_tol=1e-12, abs_tol=0)
        if not valid: raise ValueError('MOR native setting differs: '+key)
    block.ExtractStateSpaceModel('', '')
    dc, metrics = data.audit_fit(exports, f[indices], s[indices], p['reference_ohm'], p['limits'])
    adapter.select('Block', name).Delete()
    if adapter.select('Block', name).DoesExist() or snapshot(app, p['block_name']) != original:
        raise ValueError('Original circuit changed during temporary fitting')
    if observe(app, p, project_path) != before: raise ValueError('Original payload changed during fit')
    combined_f = np.r_[0., f]; combined_s = np.concatenate((dc[None], s))
    data.write_touchstone(p['output_path'], combined_f, combined_s, p['reference_ohm'])
    ff, ss = data.read_touchstone(p['output_path'], len(p['physical_port_ids']), p['reference_ohm'])
    metrics['roundtrip_error'] = float(np.max(np.abs(ss-combined_s)))
    if not np.array_equal(ff, combined_f) or metrics['roundtrip_error'] > p['limits']['roundtrip_error']:
        raise ValueError('Generated DC + positive matrix failed full roundtrip')
    if data.digest(p['matrix_path']) != p['matrix_sha256']: raise ValueError('Source changed during fitting')
    output_sha = data.digest(p['output_path'])
    artifacts = [{'path': str(Path(v).resolve()), 'sha256': data.digest(v)}
                 for v in [p['matrix_path'], str(lf_path), *exports.values(), p['output_path']]]
    adapter.select('Block', p['block_name']).SetFile(str(Path(p['output_path']).resolve()))
    facade = getattr(app, '_circuit_facade', None)
    if facade is not None: facade._spec = None
    save()
    after = observe(app, p, project_path)
    if (after['sha256'] != output_sha or after['pins'] != before['pins']
            or snapshot(app, p['block_name']) != original):
        raise ValueError('Saved embedded payload or original circuit differs')
    if any(data.digest(v['path']) != v['sha256'] for v in artifacts):
        raise ValueError('Fitting artifacts changed during target update')
    return {'before': before, 'after': after, 'topology': original, 'artifacts': artifacts,
            'metrics': metrics, 'settings_readback': actual, 'temporary_block': name,
            'payload_verified': True, 'independent_dc_verified': False, 'solver_verified': False}
