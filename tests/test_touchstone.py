import numpy as np
import pytest

from cst_automation.touchstone import write_touchstone


def test_touchstone_writer_rejects_invalid_matrix_and_existing_file(tmp_path):
    path = tmp_path / 'bad.s2p'
    with pytest.raises(ValueError, match='matrix'):
        write_touchstone(path, [1, 2], np.ones((2, 2)), 50,
                         frequency_unit='GHz')
    matrix = np.zeros((2, 2, 2), dtype=complex)
    write_touchstone(path, [1, 2], matrix, 50, frequency_unit='GHz')
    with pytest.raises(FileExistsError):
        write_touchstone(path, [1, 2], matrix, 50, frequency_unit='GHz')
