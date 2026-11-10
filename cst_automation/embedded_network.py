"""SDK-free matrix, fitting and file predicates for an embedded HB handoff."""
from pathlib import Path
import hashlib
import re
import zipfile

import numpy as np

from .em_network import finite, sha, text

CAPABILITY = 'embedded-hb-network-v1'
OPERATION = 'prepare_hb_embedded_network'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(p):
    keys = {'project_id', 'em_job_id', 'run_id', 'matrix_path', 'matrix_sha256',
            'physical_port_ids', 'native_reference_ohms', 'reference_ohm',
            'low_frequencies_hz', 'frequency_atol_hz', 'block_name',
            'expected_payload_sha256', 'output_path', 'settings', 'limits'}
    if not isinstance(p, dict) or set(p) != keys:
        raise ValueError('Exact embedded handoff fields required')
    for key in ('project_id', 'em_job_id', 'block_name'): text(p[key])
    if type(p['run_id']) is not int or p['run_id'] <= 0:
        raise ValueError('Positive native EM Run ID required')
    for key in ('matrix_sha256', 'expected_payload_sha256'): sha(p[key])
    ports = p['physical_port_ids']
    if (not isinstance(ports, list) or not 1 <= len(ports) <= 128
            or any(type(v) is not int or v <= 0 for v in ports) or len(set(ports)) != len(ports)):
        raise ValueError('Unique ordered positive physical port IDs required')
    refs = p['native_reference_ohms']
    if not isinstance(refs, list) or len(refs) != len(ports):
        raise ValueError('Explicit native reference for every physical port required')
    for v in refs: finite(v, positive=True)
    finite(p['reference_ohm'], positive=True)
    fs = p['low_frequencies_hz']
    if not isinstance(fs, list) or not 3 <= len(fs) <= 10000:
        raise ValueError('At least three actual LF samples required')
    for v in fs: finite(v, positive=True)
    if any(a >= b for a, b in zip(fs, fs[1:])):
        raise ValueError('LF frequencies must be strictly increasing')
    atol = finite(p['frequency_atol_hz'])
    if not 0 <= atol < min(fs[0], min(np.diff(fs)) / 2):
        raise ValueError('Frequency tolerance may not alias LF samples or DC')
    for key in ('matrix_path', 'output_path'):
        if not isinstance(p[key], str) or not Path(p[key]).is_absolute():
            raise ValueError('Absolute source/output paths required')
    if Path(p['matrix_path']).suffix.lower() != '.npz' or Path(p['output_path']).suffix.lower() != f'.s{len(ports)}p':
        raise ValueError('Expected NPZ source and matching .sNp output')
    s = p['settings']
    if not isinstance(s, dict) or set(s) != {'accuracy_abs', 'maximum_poles', 'enhance_dc', 'passivate'}:
        raise ValueError('Explicit fitting settings required')
    if not 0 < finite(s['accuracy_abs']) < 1: raise ValueError('Invalid fitting accuracy')
    if type(s['maximum_poles']) is not int or not 1 <= s['maximum_poles'] <= 1000:
        raise ValueError('Bounded pole count required')
    for key in ('enhance_dc', 'passivate'):
        if type(s[key]) is not bool: raise ValueError('Boolean fitting flags required')
    limits = p['limits']
    if not isinstance(limits, dict) or set(limits) != {'fit_max_error', 'dc_solve_residual',
            'dc_max_singular', 'dc_reciprocity_error', 'roundtrip_error', 'native_matrix_error', 'native_sample_residual'}:
        raise ValueError('Explicit independent numerical limits required')
    for v in limits.values(): finite(v, positive=True)
    if any(v >= 1 for k, v in limits.items() if k != 'dc_max_singular'):
        raise ValueError('Error limits must be below one')


def load_matrix(p):
    validate(p)
    path = Path(p['matrix_path'])
    if path.stat().st_size > 256_000_000 or digest(path) != p['matrix_sha256']:
        raise ValueError('Source matrix size or digest differs')
    with zipfile.ZipFile(path) as archive:
        if sum(i.file_size for i in archive.infolist()) > 256_000_000:
            raise ValueError('Expanded source matrix exceeds limit')
    with np.load(path, allow_pickle=False) as data:
        frequency = set(data.files) & {'frequency_hz', 'frequency_GHz'}
        if len(frequency) != 1 or set(data.files) != {'S', 'ports'} | frequency:
            raise ValueError('Exact matrix keys required')
        key = frequency.pop()
        if data[key].dtype.kind not in 'fiu': raise ValueError('Real numeric frequency axis required')
        f = np.asarray(data[key], dtype=float) * (1e9 if key == 'frequency_GHz' else 1)
        ports = np.asarray(data['ports'])
        s = np.asarray(data['S'], dtype=complex)
    n = len(p['physical_port_ids'])
    if (ports.dtype.kind not in 'iu' or ports.tolist() != p['physical_port_ids']
            or f.ndim != 1 or len(f) < 3 or s.shape != (len(f), n, n) or s.size > 2_000_000
            or not np.isfinite(f).all() or not np.isfinite(s).all()
            or f[0] <= 0 or not np.all(np.diff(f) > 0)):
        raise ValueError('Complete finite positive-frequency matrix in explicit port order required')
    indices = []
    for required in p['low_frequencies_hz']:
        hits = np.flatnonzero(np.abs(f - required) <= p['frequency_atol_hz'])
        if len(hits) != 1: raise ValueError('Required actual LF sample missing or ambiguous')
        indices.append(int(hits[0]))
    if len(set(indices)) != len(indices): raise ValueError('LF samples alias')
    if digest(path) != p['matrix_sha256']: raise ValueError('Source changed during reading')
    return f, s, indices


def renormalize(s, old_refs, new_ref):
    """Real-reference power waves; right division without an explicit inverse."""
    d = np.sqrt(np.asarray(old_refs, dtype=float) / new_ref)
    a, b = np.diag((d + 1 / d) / 2), np.diag((d - 1 / d) / 2)
    out = np.asarray([np.linalg.solve((a + b @ row).T, (b + a @ row).T).T for row in s])
    if not np.isfinite(out).all(): raise ValueError('Nonfinite renormalized matrix')
    return out


def actual_lf_samples(log, p):
    """Final-mesh native excitations, not interpolated saved curve rows."""
    marker = 'Mesh adaptation terminated because the desired accuracy limit is reached.'
    if log.count(marker) != 1:
        raise ValueError('Unique final-mesh boundary required for actual LF samples')
    body = log.split(marker, 1)[1]
    end = 'Finished the general purpose interpolative broadband frequency sweep:'
    if body.count(end) != 1: raise ValueError('Final broadband sweep boundary missing')
    body = body.split(end, 1)[0]
    body = re.sub(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s+', '', body, flags=re.M)
    pattern = (r'Calculation \d+(?: of \d+)? \(Frequency: ([0-9.eE+-]+) (Hz|kHz|MHz|GHz)\)'
               r'|Stimulation port\s*:\s*(\d+)\s+Accuracy\s*:\s*([0-9.eE+-]+)\s+Iterations\s*:')
    frequency = None; rows = []
    for match in re.finditer(pattern, body):
        if match.group(1):
            frequency = float(match.group(1))*{'Hz':1, 'kHz':1e3, 'MHz':1e6, 'GHz':1e9}[match.group(2)]
        elif frequency is not None:
            rows.append((frequency, int(match.group(3)), float(match.group(4))))
    proof = []
    for required in p['low_frequencies_hz']:
        for port in p['physical_port_ids']:
            hits = [(f, r) for f, v, r in rows if v == port and abs(f-required) <= p['frequency_atol_hz']]
            if not hits or any(not np.isfinite(r) or not 0 <= r <= p['limits']['native_sample_residual'] for _, r in hits):
                raise ValueError('Actual final-mesh LF excitation absent or residual excessive')
            proof.append({'frequency_hz': required, 'port_id': port, 'max_residual': max(r for _, r in hits)})
    return proof


def write_touchstone(path, f, s, reference):
    """Exclusive file creation, v1 full RI; two-port ordering is column-major."""
    n = s.shape[1]
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(f'# Hz S RI R {reference:.17g}\n')
        for frequency, row in zip(f, s):
            entries = row.T.ravel() if n == 2 else row.ravel()
            stream.write(' '.join([format(frequency, '.17g')] +
                         [format(v, '.17g') for z in entries for v in (z.real, z.imag)]) + '\n')


def read_touchstone(path, n, reference):
    lines = Path(path).read_text(encoding='utf-8-sig').splitlines()
    if not lines or lines[0].split() != ['#', 'Hz', 'S', 'RI', 'R', format(reference, '.17g')]:
        raise ValueError('Unexpected generated Touchstone header')
    rows = np.asarray([[float(v) for v in line.split()] for line in lines[1:]])
    if rows.ndim != 2 or rows.shape[1] != 1 + 2*n*n or not np.isfinite(rows).all():
        raise ValueError('Incomplete generated Touchstone')
    s = (rows[:, 1::2] + 1j*rows[:, 2::2]).reshape(-1, n, n)
    if n == 2: s = s.transpose(0, 2, 1)
    return rows[:, 0], s


def audit_fit(paths, f, s, reference, limits):
    log = Path(paths['log']).read_text(encoding='utf-8-sig')
    if not all(t in log for t in ('Scattering formulation', 'dx/dt = [A] * x + [B] * u', 'y     = [C] * x + [D] * u')):
        raise ValueError('Unknown state-space formulation')
    n = s.shape[1]
    reference_section = log.split('Reference impedances:')[1].split('Port labels:')[0]
    refs = re.findall(r'Port\s+(\d+):\s*([0-9.eE+-]+)\s+Ohm', reference_section)
    if refs != [(str(i+1), value) for i, (_, value) in enumerate(refs)] or len(refs) != n or any(float(v) != reference for _, v in refs):
        raise ValueError('MOR reference impedances differ')
    labels = re.findall(r'Port\s+(\d+):\s*"(\d+)"', log.split('Port labels:')[1])
    if labels != [(str(i), str(i)) for i in range(1, n+1)]: raise ValueError('MOR port order differs')
    errors = re.findall(r'Achieved accuracy in vector fitting of S-Parameters:\s*([0-9.eE+-]+)', log)
    if len(errors) != 1: raise ValueError('Unique MOR accuracy missing')
    reported = float(errors[0])
    matrices = []
    for key in 'ABCD':
        path = Path(paths[key])
        if path.stat().st_size > 64_000_000: raise ValueError('MOR export exceeds limit')
        data = np.loadtxt(path, delimiter=',', ndmin=2)
        if not np.isfinite(data).all(): raise ValueError('Nonfinite MOR matrix')
        matrices.append(data)
    a, b, c, d = matrices
    states = a.shape[0]
    if (states > 4000 or a.shape != (states, states) or b.shape != (states, n)
            or c.shape != (n, states) or d.shape != (n, n)):
        raise ValueError('MOR matrix dimensions differ')
    for name, count in (('x', states), ('u', n), ('y', n)):
        if re.findall(r'dim\(' + name + r'\)\s*=\s*(\d+)', log) != [str(count)]:
            raise ValueError('Native MOR dimensions disagree with exports')
    ab = np.linalg.solve(a, b)
    dc = d - c @ ab
    residual = float(np.linalg.norm(a @ ab - b) / max(np.linalg.norm(b), np.finfo(float).tiny))
    reconstructed = np.asarray([d + c @ np.linalg.solve(2j*np.pi*v*np.eye(states)-a, b) for v in f])
    metrics = {'fit_max_error': max(reported, float(np.max(np.abs(reconstructed-s)))),
               'dc_solve_residual': residual,
               'dc_max_singular': float(np.linalg.svd(dc, compute_uv=False)[0]),
               'dc_reciprocity_error': float(np.max(np.abs(dc-dc.T)))}
    if not np.isfinite(reported) or reported < 0 or not np.isfinite(dc).all():
        raise ValueError('Invalid fit/DC result')
    for key, value in metrics.items():
        if not np.isfinite(value) or value > limits[key]: raise ValueError('Numerical limit failed: '+key)
    return dc, metrics
