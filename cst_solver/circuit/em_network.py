"""Bounded native block fitting and file update; no app creation or HB execution."""
from pathlib import Path
import hashlib
import math

MOR = {
    'fmax': ('SetConvolutionFmax','GetConvolutionFmax'),
    'accuracy_abs': ('SetMOR_AccuracyAbs','GetMOR_AccuracyAbs'),
    'enhance_dc': ('SetMOR_EnhanceAccuracyAtDC','GetMOR_EnhanceAccuracyAtDC'),
    'passivate': ('SetMOR_PassivateToInfinity','GetMOR_PassivateToInfinity'),
    'method': ('SetVectorFittingMethod','GetVectorFittingMethod'),
    'error_norm': ('SetMOR_ErrorNorm','GetMOR_ErrorNorm'),
    'natural_impedances': ('SetUseNaturalImpedances','GetUseNaturalImpedances'),
    'reference_ohm': ('SetMOR_RenormalizationImpedance','GetMOR_RenormalizationImpedance'),
}
POLES = {
    'manual_pole_choice': ('SetMOR_ManualPoleChoice', 'GetMOR_ManualPoleChoice'),
    'initial_poles': ('SetMOR_InitialPoles', 'GetMOR_InitialPoles'),
    'maximum_poles': ('SetMOR_MaximumPoles', 'GetMOR_MaximumPoles'),
    'pole_increment': ('SetMOR_PoleIncrement', 'GetMOR_PoleIncrement'),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def observe(app, p, *, file_block=False):
    block = app.circuit.adapter.select('Block', p['block_name'])
    if not block.DoesExist() or str(block.GetTypeName()) != p['expected_type']:
        raise ValueError('Native block identity differs')
    count = block.GetNumberOfPorts()
    if type(count) is not int or count != len(p['expected_ports']):
        raise ValueError('Native block port count differs')
    ports = [str(block.GetPortName(i)) for i in range(count)]
    if ports != p['expected_ports']: raise ValueError('Native ordered ports differ')
    data = {'type':str(block.GetTypeName()), 'ports':ports}
    if file_block:
        if block.GetNumberOfFiles() != 1 or block.IsCachingFiles() is not False:
            raise ValueError('Only one uncached file is supported')
        path = Path(str(block.GetFile()))
        if not path.is_absolute() or not path.is_file(): raise ValueError('Native absolute file unavailable')
        data.update(path=str(path.resolve()), sha256=digest(path))
    return block, data


def fit(app, p, project_path):
    from cst_automation.em_network import validate
    validate('fit_em_network',p)
    block, before = observe(app,p)
    source = str(block.GetFile())
    if source and (not Path(source).is_absolute() or Path(source).resolve()!=Path(project_path).resolve()):
        raise ValueError('Fitting requires the intrinsic same-project EM block')
    before['source_file']=source
    directory=Path(project_path).with_suffix('')/'Export'/'ABCD'
    if any(directory.glob(p['block_name']+'*')):
        raise ValueError('Existing block exports must be archived before fitting')
    if block.CanUseMOR() is not True: raise ValueError('Block does not support MOR')
    # Resolve every getter/setter before the first setting mutation.
    selected = dict(MOR)
    selected.update((key, pair) for key, pair in POLES.items() if key in p['settings'])
    old = {key:getattr(block,getter)() for key,(_,getter) in selected.items()}
    setters = {key:getattr(block,setter) for key,(setter,_) in selected.items()}
    extract = block.ExtractStateSpaceModel
    # Native manual mode must be chosen before initial count or increment.
    for key in selected:
        value = p['settings'][key]
        setters[key](value if type(value) is bool else str(value))
    actual = {key:getattr(block,getter)() for key,(_,getter) in selected.items()}
    for key,value in p['settings'].items():
        got=actual[key]
        if type(value) is bool:
            valid = type(got) is bool and got == value
        elif type(value) in (int,float):
            valid = math.isclose(float(got),value,rel_tol=1e-12,abs_tol=0)
        else: valid = str(got) == value
        if not valid: raise ValueError('Native MOR setting readback differs: '+key)
    extract(str(p['settings']['fmax']), '')
    block, after = observe(app,p)
    after['source_file']=str(block.GetFile())
    if before != after: raise ValueError('Block identity changed during fitting')
    artifacts = []
    for key,path in p['export_paths'].items():
        source=Path(path)
        if not source.is_file() or source.stat().st_size == 0: raise ValueError('Missing MOR export: '+key)
        artifacts.append({'path':str(source.resolve()),'sha256':digest(source)})
    return {'before':before,'settings_before':old,'settings_readback':actual,'artifacts':artifacts,
            'native_call_returned':True,'numerical_fit_verified':False,'dc_verified':False}


def update(app,p):
    from cst_automation.em_network import validate, touchstone
    validate('update_hb_network',p)
    touchstone(p['path'],len(p['expected_ports']),p['reference_ohm'],p['fmax_hz'])
    block,before = observe(app,p,file_block=True)
    if before['sha256'] != p['expected_file_sha256']: raise ValueError('Original block file changed')
    if digest(p['path']) != p['sha256']: raise ValueError('New block file changed')
    block.SetFile(str(Path(p['path']).resolve()))
    facade=getattr(app,'_circuit_facade',None)
    if facade is not None: facade._spec=None
    _,after=observe(app,p,file_block=True)
    if after['path'].casefold()!=str(Path(p['path']).resolve()).casefold() or after['sha256']!=p['sha256']:
        raise ValueError('Native file update readback differs')
    return {'before':before,'after':after,'file_readback_verified':True,'solver_verified':False}
