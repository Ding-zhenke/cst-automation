"""Offline parsing of saved CST ModelCache material state."""
import hashlib

import pytest
from cst_automation.material_snapshot import MaterialSnapshotError, read_gyrotropic_material


BLOCK = '''[MATERIAL: Ferrite]
     .Type "Normal"
     .MaterialUnit "Frequency", "Hz"
     .DispModelMu "Gyrotropic"
     .UseSISystem "True"
     .DispCoeff1Mu "1000"
     .DispCoeff2Mu "200"
     .DispCoeff3Mu "0.02"
     .DispCoeff4MuX "0"
     .DispCoeff4MuY "0"
     .DispCoeff4MuZ "1"
[ENDMATERIAL]
'''


def _saved_project(tmp_path, mif_text=BLOCK):
    project = tmp_path / 'model.cst'
    project.write_bytes(b'fixture CST project')
    cache = tmp_path / 'model' / 'ModelCache'
    cache.mkdir(parents=True)
    mif = cache / 'Model.mif'
    mif.write_text(mif_text, encoding='utf-8')
    return project, mif


def test_reads_exact_si_gyrotropic_material_from_saved_cache(tmp_path):
    project, mif = _saved_project(tmp_path)

    result = read_gyrotropic_material(project, 'Ferrite')

    assert result['material_name'] == 'Ferrite'
    assert result['larmor_rad_s'] == pytest.approx(1000)
    assert result['gyro_rad_s'] == pytest.approx(200)
    assert result['damping'] == pytest.approx(0.02)
    assert result['bias_direction'] == (0.0, 0.0, 1.0)
    assert result['source_path'] == str(mif.resolve())
    assert result['sha256'] == hashlib.sha256(mif.read_bytes()).hexdigest()
    assert result['evidence_type'] == 'saved_model_cache'
    assert 'saved' in result['source_summary'].lower()


def test_ignores_repeated_unrelated_material_unit_records(tmp_path):
    repeated = BLOCK.replace(
        '     .MaterialUnit "Frequency", "Hz"\n',
        '     .MaterialUnit "Frequency", "Hz"\n'
        '     .MaterialUnit "Geometry", "mm"\n'
        '     .MaterialUnit "Time", "s"\n')
    project, _ = _saved_project(tmp_path, repeated)

    result = read_gyrotropic_material(project, 'Ferrite')

    assert result['larmor_rad_s'] == pytest.approx(1000)


def test_rejects_duplicate_target_field_with_case_variation(tmp_path):
    repeated = BLOCK.replace(
        '     .DispCoeff1Mu "1000"\n',
        '     .DispCoeff1Mu "1000"\n     .dispcoeff1mu "1000"\n')
    project, _ = _saved_project(tmp_path, repeated)

    with pytest.raises(MaterialSnapshotError):
        read_gyrotropic_material(project, 'Ferrite')


def test_preserves_negative_z_bias_direction(tmp_path):
    negative_z = BLOCK.replace('.DispCoeff4MuZ "1"', '.DispCoeff4MuZ "-1"')
    project, _ = _saved_project(tmp_path, negative_z)

    result = read_gyrotropic_material(project, 'Ferrite')

    assert result['bias_direction'] == (0.0, 0.0, -1.0)


def test_material_name_match_is_exact(tmp_path):
    project, _ = _saved_project(tmp_path)

    with pytest.raises(MaterialSnapshotError):
        read_gyrotropic_material(project, 'ferrite')


@pytest.mark.parametrize('replacement', [
    ('.Type "Normal"', '.Type "Anisotropic"'),
    ('.DispModelMu "Gyrotropic"', '.DispModelMu "None"'),
    ('.UseSISystem "True"', '.UseSISystem "False"'),
])
def test_rejects_non_normal_non_gyrotropic_or_non_si_material(tmp_path, replacement):
    project, _ = _saved_project(tmp_path, BLOCK.replace(*replacement))

    with pytest.raises(MaterialSnapshotError):
        read_gyrotropic_material(project, 'Ferrite')


@pytest.mark.parametrize('line', [
    '     .DispCoeff1Mu "1000"\n',
    '     .DispCoeff2Mu "200"\n',
    '     .DispCoeff3Mu "0.02"\n',
    '     .DispCoeff4MuX "0"\n',
    '     .DispCoeff4MuY "0"\n',
    '     .DispCoeff4MuZ "1"\n',
])
def test_rejects_missing_gyrotropic_field_instead_of_using_history(tmp_path, line):
    project, _ = _saved_project(tmp_path, BLOCK.replace(line, ''))
    history = tmp_path / 'model' / 'Model' / '3D'
    history.mkdir(parents=True)
    (history / 'ModelHistory.json').write_text(
        '{"code":"' + BLOCK.replace('"', '\\"').replace('\n', '\\n') + '"}',
        encoding='utf-8')

    with pytest.raises(MaterialSnapshotError):
        read_gyrotropic_material(project, 'Ferrite')


@pytest.mark.parametrize('bad_value', [
    'not-a-number', 'nan', 'inf', '-1',
])
def test_rejects_invalid_angular_frequency(tmp_path, bad_value):
    project, _ = _saved_project(
        tmp_path, BLOCK.replace('"1000"', f'"{bad_value}"'))

    with pytest.raises(MaterialSnapshotError):
        read_gyrotropic_material(project, 'Ferrite')


@pytest.mark.parametrize('bad_direction', [
    ('0', '0', '2'), ('0', '0', 'nan'), ('0', '0', '-inf'),
])
def test_rejects_invalid_bias_direction_without_normalizing(tmp_path, bad_direction):
    text = BLOCK.replace('.DispCoeff4MuX "0"', f'.DispCoeff4MuX "{bad_direction[0]}"')
    text = text.replace('.DispCoeff4MuY "0"', f'.DispCoeff4MuY "{bad_direction[1]}"')
    text = text.replace('.DispCoeff4MuZ "1"', f'.DispCoeff4MuZ "{bad_direction[2]}"')
    project, _ = _saved_project(tmp_path, text)

    with pytest.raises(MaterialSnapshotError):
        read_gyrotropic_material(project, 'Ferrite')


@pytest.mark.parametrize('mif_text', [
    BLOCK + BLOCK,
    '[ENDMATERIAL]\n' + BLOCK,
    BLOCK.replace('[ENDMATERIAL]', ''),
    BLOCK.replace('[MATERIAL: Ferrite]',
                  '[MATERIAL: Ferrite]\n[MATERIAL: Nested]'),
])
def test_rejects_ambiguous_or_malformed_material_block_segmentation(tmp_path, mif_text):
    project, _ = _saved_project(tmp_path, mif_text)

    with pytest.raises(MaterialSnapshotError):
        read_gyrotropic_material(project, 'Ferrite')


def test_rejects_missing_cst_or_model_cache_file(tmp_path):
    project = tmp_path / 'missing.cst'

    with pytest.raises(MaterialSnapshotError):
        read_gyrotropic_material(project, 'Ferrite')

    project.write_bytes(b'fixture CST project')
    with pytest.raises(MaterialSnapshotError):
        read_gyrotropic_material(project, 'Ferrite')
