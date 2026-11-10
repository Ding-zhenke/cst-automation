"""Strict, SDK-free inputs for the EM fit -> HB network handoff."""
import math
import re
from pathlib import Path

CAPABILITY = 'em-network-input-v1'
OPERATIONS = frozenset(('fit_em_network', 'update_hb_network'))


def finite(value, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or (positive and value <= 0):
        raise ValueError('Finite positive numeric value required' if positive else 'Finite number required')
    return value


def text(value):
    if not isinstance(value, str) or not value or len(value) > 512 or any(ord(c) < 32 for c in value):
        raise ValueError('Bounded explicit text required')


def sha(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Explicit SHA-256 required')


def validate(operation, p):
    common = {'project_id','em_job_id','block_name','expected_type','expected_ports'}
    extra = {'settings','export_paths'} if operation == 'fit_em_network' else {
        'fit_job_id','expected_file_sha256','path','sha256','reference_ohm','fmax_hz','max_fit_error'}
    if not isinstance(p, dict) or set(p) != common | extra:
        raise ValueError('Exact EM network operation fields required')
    for key in common - {'expected_ports'}: text(p[key])
    if not re.fullmatch(r'[A-Za-z0-9_ -]+', p['block_name']):
        raise ValueError('This export interface requires a simple block name')
    ports = p['expected_ports']
    if not isinstance(ports, list) or not 1 <= len(ports) <= 128 or len(set(ports)) != len(ports):
        raise ValueError('Explicit unique ordered port names required')
    for port in ports: text(port)
    if operation == 'fit_em_network':
        if p['expected_type'].lower() not in ('cstmws', 'cst microwave studio'):
            raise ValueError('Only the intrinsic same-project EM block is supported')
        s = p['settings']
        if not isinstance(s, dict) or set(s) != {'fmax','accuracy_abs','enhance_dc','passivate','method','error_norm','natural_impedances','reference_ohm'}:
            raise ValueError('Explicit MOR settings required')
        for key in ('fmax','accuracy_abs','reference_ohm'): finite(s[key], positive=True)
        if s['accuracy_abs'] >= 1: raise ValueError('MOR accuracy must be below 1')
        for key in ('enhance_dc','passivate','natural_impedances'):
            if type(s[key]) is not bool: raise ValueError('MOR flags must be booleans')
        if s['method'] not in ('BUILT-IN','IDEM') or s['error_norm'] not in ('Max','L2'):
            raise ValueError('Unsupported MOR method/norm')
        exports = p['export_paths']
        if not isinstance(exports, dict) or set(exports) != {'A','B','C','D','log'}:
            raise ValueError('Explicit ABCD matrix and native log paths required')
        paths = []
        for path in exports.values():
            if not isinstance(path,str) or not Path(path).is_absolute(): raise ValueError('Absolute export paths required')
            paths.append(str(Path(path).resolve()).casefold())
        if len(set(paths)) != 5: raise ValueError('Distinct exports required')
    else:
        text(p['fit_job_id']); sha(p['sha256']); sha(p['expected_file_sha256'])
        for key in ('reference_ohm','fmax_hz','max_fit_error'): finite(p[key], positive=True)
        if p['expected_type'].lower() != 'touchstone file':
            raise ValueError('Only uncached Touchstone file blocks supported')
        if not isinstance(p['path'],str) or not Path(p['path']).is_absolute(): raise ValueError('Absolute input path required')


def touchstone(path, nports, reference_ohm, fmax_hz):
    """Validate full v1 S/RI data, including every complex entry and DC row."""
    path = Path(path)
    if path.suffix.lower() != f'.s{nports}p' or path.stat().st_size > 256_000_000:
        raise ValueError('Bounded matching .sNp file required')
    header = None
    values = []
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.split('!',1)[0].strip()
        if not line: continue
        if line.startswith('#'):
            if header is not None or values: raise ValueError('Single initial option line required')
            header = line[1:].upper().split()
            if len(header) != 5 or header[0] not in ('HZ','KHZ','MHZ','GHZ') or header[1:4] != ['S','RI','R']:
                raise ValueError('Explicit Touchstone v1 S RI R format required')
            if float(header[4]) != reference_ohm: raise ValueError('Reference impedance differs')
        else:
            if header is None: raise ValueError('Missing option line')
            values.extend(float(v) for v in line.split())
    width = 1 + 2*nports*nports
    if header is None or len(values) < 2*width or len(values) % width or not all(math.isfinite(v) for v in values):
        raise ValueError('Complete finite full-matrix samples required')
    scale = {'HZ':1,'KHZ':1e3,'MHZ':1e6,'GHZ':1e9}[header[0]]
    frequencies = [v*scale for v in values[::width]]
    if frequencies[0] != 0 or any(a >= b for a,b in zip(frequencies,frequencies[1:])) or frequencies[-1] < fmax_hz:
        raise ValueError('Strictly ordered DC-through-band samples required')
    return {'ports':nports,'samples':len(frequencies),'fmin_hz':0,'fmax_hz':frequencies[-1], 'reference_ohm':reference_ohm}
