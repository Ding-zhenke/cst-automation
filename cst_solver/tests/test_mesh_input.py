import pytest


def sample():
    # Independently encoded definite CBOR: {Attributes: {i/curvature_order: 2}}
    return b'\xa1\x6aAttributes\xa1\x71i/curvature_order\x02'


def test_saved_input_is_read_only_and_reports_all_attributes(tmp_path):
    from cst_solver.mesh_input import read_saved_options
    path = tmp_path / 'Mesh_Input.Options.tet'; path.write_bytes(sample())
    result = read_saved_options(path)
    assert result['attributes'] == {'i/curvature_order': 2}
    assert result['live_getter'] is False and result['source_job_binding'] == 'not_verified'
    assert path.read_bytes() == sample()


@pytest.mark.parametrize('raw', [b'', b'\xbf\xff', b'\xa2\x61a\x01\x61a\x02',
                               b'\x9a\xff\xff\xff\xff', sample()[:-1], sample()+b'\x00',
                               b'\xfb\x7f\xf0\x00\x00\x00\x00\x00\x00'])
def test_invalid_or_unbounded_input_fails(tmp_path, raw):
    from cst_solver.mesh_input import read_saved_options
    path = tmp_path / 'options.tet'; path.write_bytes(raw)
    with pytest.raises(ValueError):
        read_saved_options(path)
