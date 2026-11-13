import numpy as np
import pytest

from cst_automation.touchstone import write_touchstone


@pytest.mark.parametrize('nports', [1, 2, 3, 4])
def test_touchstone_v1_column_major_roundtrip_text(tmp_path, nports):
    matrix = (np.arange(2 * nports * nports).reshape(2, nports, nports)
              + 1j * np.arange(2 * nports * nports, 4 * nports * nports).reshape(2, nports, nports)
              ).astype(complex)
    path = tmp_path / f'point.s{nports}p'
    write_touchstone(path, [1, 2], matrix, 50, frequency_unit='GHz')

    first = [float(value) for value in path.read_text().splitlines()[1].split()]
    expected = matrix[0].T.reshape(-1)
    assert first[0] == 1
    assert np.array_equal(np.asarray(first[1::2]) + 1j * np.asarray(first[2::2]), expected)


def test_touchstone_writer_rejects_invalid_matrix_and_existing_file(tmp_path):
    path = tmp_path / 'bad.s2p'
    with pytest.raises(ValueError, match='matrix'):
        write_touchstone(path, [1, 2], np.ones((2, 2)), 50,
                         frequency_unit='GHz')
    matrix = np.zeros((2, 2, 2), dtype=complex)
    write_touchstone(path, [1, 2], matrix, 50, frequency_unit='GHz')
    with pytest.raises(FileExistsError):
        write_touchstone(path, [1, 2], matrix, 50, frequency_unit='GHz')
