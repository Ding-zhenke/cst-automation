from types import SimpleNamespace
import re
from base64 import b64decode

import pytest

from cst_solver.postprocessing.result_export import ExportMixin, _validate_complex_field


HEADER = 'x [mm] y [mm] z [mm] ExRe [V/m] ExIm [V/m] EyRe [V/m] EyIm [V/m] EzRe [V/m] EzIm [V/m]\n'


class Host(ExportMixin):
    def __init__(self, content):
        self.code = ''
        def execute(code):
            self.code = code
            path = re.search(r'(?:\.FileName|Plot.ExportImage) "([^"]+)"', code).group(1)
            with open(path, 'wb') as stream:
                stream.write(content)
        self.cst_file = SimpleNamespace(model3d=SimpleNamespace(_execute_vba_code=execute))


def test_complex_export_checks_selection_and_samples(tmp_path):
    host = Host((HEADER + '-----\n1 2 3 4 5 6 7 8 9\n').encode())
    result = host.export_complex_field_ascii('2D/3D Results\\E-Field\\x', str(tmp_path / 'f.txt'), 0.5)
    assert result == str(tmp_path / 'f.txt')
    assert 'If Not SelectTreeItem(' in host.code
    assert 'GetSelectedTreeItem()' in host.code
    assert '.Mode "FixedWidth"' in host.code and '.Step 0.5' in host.code


def test_bad_field_preserves_existing_file(tmp_path):
    target = tmp_path / 'f.txt'
    target.write_text('original')
    host = Host((HEADER + '-----\n1 2 3 4 5 6 7 8 9\n1 2 3\n').encode())
    with pytest.raises(ValueError):
        host.export_complex_field_ascii('2D/3D Results\\E-Field\\x', str(target))
    assert target.read_text() == 'original'


def test_model_capture_selects_components(tmp_path):
    host = Host(b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC'
                          'AAAAC0lEQVR42mP8/x8AAwMCAO+/aRkAAAAASUVORK5CYII='))
    host.capture_model_view_png(str(tmp_path / 'model.png'))
    assert 'SelectTreeItem("Components")' in host.code
    assert 'GetSelectedTreeItem()' in host.code


def test_header_rejects_noncomplex(tmp_path):
    path = tmp_path / 'field.txt'
    path.write_text('x [mm] y [mm] z [mm] Abs [V/m]\n----\n1 2 3 4\n')
    with pytest.raises(ValueError):
        _validate_complex_field(path)
