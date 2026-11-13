"""Small, explicit Touchstone v1 full-matrix writer."""
from pathlib import Path
import math

import numpy as np


FREQUENCY_UNITS = {'Hz', 'kHz', 'MHz', 'GHz', 'THz'}


def write_touchstone(path, frequencies, s_matrix, reference_ohm, *,
                     frequency_unit, comments=()):
    """Write one full S matrix per frequency using Touchstone v1 RI ordering.

    ``s_matrix[k, i, j]`` is written using Touchstone's column-major sequence
    (S11, S21, ..., SN1, S12, ...). S values are preserved as supplied; this
    function does not renormalize them.
    """
    path = Path(path)
    if frequency_unit not in FREQUENCY_UNITS:
        raise ValueError('frequency_unit must be Hz, kHz, MHz, GHz or THz')
    if type(reference_ohm) not in (int, float) or not math.isfinite(reference_ohm) or reference_ohm <= 0:
        raise ValueError('reference_ohm must be finite and positive')
    f = np.asarray(frequencies, dtype=float)
    s = np.asarray(s_matrix, dtype=complex)
    if (f.ndim != 1 or not f.size or s.ndim != 3 or s.shape[0] != len(f)
            or s.shape[1] != s.shape[2] or not s.shape[1]
            or not np.isfinite(f).all() or np.any(f < 0)
            or not np.all(np.diff(f) > 0) or not np.isfinite(s).all()):
        raise ValueError('Finite, ordered frequencies and a complete finite square S matrix are required')
    if not isinstance(comments, (list, tuple)) or any(
            not isinstance(line, str) or '\n' in line or '\r' in line for line in comments):
        raise ValueError('comments must be single-line strings')

    n = s.shape[1]
    if path.suffix.lower() != f'.s{n}p':
        raise ValueError('Touchstone suffix must match the matrix port count')
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        for comment in comments:
            stream.write(f'! {comment}\n')
        stream.write(f'# {frequency_unit} S RI R {float(reference_ohm):.17g}\n')
        for frequency, matrix in zip(f, s):
            entries = matrix.T.reshape(-1)
            values = [format(float(frequency), '.17g')]
            for value in entries:
                values.extend((format(float(value.real), '.17g'),
                               format(float(value.imag), '.17g')))
            stream.write(' '.join(values) + '\n')
    return str(path.resolve())
