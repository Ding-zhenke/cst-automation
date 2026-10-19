import inspect

import numpy as np
import pytest

from cst_automation.curves import contiguous_bands, find_resonances
from cst_automation.s2p import read_s2p_groups


def test_contiguous_bands_keeps_gaps_and_reports_extrema():
    bands = contiguous_bands([3, 4, 5, 6], [-12, -8, -15, -10],
                             threshold_db=-10, criterion="below")
    assert [(band["fmin_ghz"], band["fmax_ghz"]) for band in bands] == [(3.0, 3.0), (5.0, 6.0)]
    assert bands[1]["best_db"] == -15.0
    assert bands[1]["worst_freq_ghz"] == 6.0


def test_find_resonances_is_sampled_local_extremum():
    found = find_resonances([1, 2, 3, 4, 5], [-2, -5, -1, -4, -2], kind="min",
                            min_prominence_db=1.5)
    assert found == [
        {"freq_ghz": 2.0, "db": -5.0, "kind": "min", "prominence_db": 3.0},
        {"freq_ghz": 4.0, "db": -4.0, "kind": "min", "prominence_db": 2.0},
    ]


def test_curves_reject_malformed_criteria_and_length_mismatch():
    with pytest.raises(ValueError, match="criterion"):
        contiguous_bands([1], [0], threshold_db=-1, criterion="sideways")
    with pytest.raises(ValueError, match="长度不一致"):
        contiguous_bands([1, 2], [0], threshold_db=-1)


def test_s2p_group_parser_preserves_array_shape_and_changed_labels(tmp_path):
    path = tmp_path / "groups.s2p"
    path.write_text(
        "#Parameters = {length=1;label=keep}\n1 0.1\n2 0.2\n"
        "#Parameters = {length=2;label=keep}\n1 0.3\n2 0.4\n",
        encoding="utf-8",
    )
    data, labels = read_s2p_groups(path)
    np.testing.assert_allclose(data, [[1, 0.1, 0.3], [2, 0.2, 0.4]])
    assert list(labels) == ["length=1", "length=2"]


def test_s2p_parser_keeps_source_signature():
    assert list(inspect.signature(read_s2p_groups).parameters) == ["filepath"]
